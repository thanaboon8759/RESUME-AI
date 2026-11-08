"""How much of an OCR CER change is formatting (Markdown / JSON wrapper) rather than reading accuracy.

Usage: python resume-lab/format_share.py <run_id>
Prints per model: raw CER (as scored) and CER after stripping markup from the model output.
"""
import json
import re
import sys
from pathlib import Path

from evaluate_models import ROOT, cer


def strip_markup(text: str) -> str:
    try:
        wrapped = json.loads(text)
        if isinstance(wrapped, dict):
            text = wrapped.get('natural_text', wrapped.get('text', ''))
    except (json.JSONDecodeError, TypeError):
        pass
    text = re.sub(r'(?m)^#{1,6}\s*', '', text)  # headings
    text = text.replace('**', '').replace('__', '')  # bold
    return text.strip()


def main(run_id):
    run = ROOT / 'evaluation/runs' / run_id
    config = json.loads((run / 'configuration.json').read_text(encoding='utf-8'))
    corpus = ROOT / 'evaluation' / config['corpus_directory']
    refs = {s['id']: (corpus / s['files']['text']).read_text(encoding='utf-8')
            for s in json.loads((corpus / 'manifest.json').read_text(encoding='utf-8'))['samples']}
    by_model = {}
    for line in (run / 'attempts.jsonl').read_text(encoding='utf-8').splitlines():
        r = json.loads(line)
        out = r['raw_responses'][-1].get('message', {}).get('content', '') if r.get('raw_responses') else ''
        by_model.setdefault(r['model'], []).append((r['metrics'].get('cer', 1.0), cer(refs[r['sample_id']], strip_markup(out))))
    for model, pairs in sorted(by_model.items()):
        raw = sum(a for a, _ in pairs) / len(pairs)
        clean = sum(b for _, b in pairs) / len(pairs)
        print(f'{model:40} raw_cer={raw:.5f} markup_stripped_cer={clean:.5f} n={len(pairs)}')


if __name__ == '__main__':
    main(sys.argv[1])
