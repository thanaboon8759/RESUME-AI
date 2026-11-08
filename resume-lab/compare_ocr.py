"""Side-by-side OCR comparison of two (or more) models on any resume files.

Reports go to compare-reports/ (git-ignored): user resumes are private and never committed.
Usage: python resume-lab/compare_ocr.py FILE [FILE ...] [--models A B] [--out compare-reports/x.html]
Default models: the v6 default (typhoon-ocr-finetuned) and the current policy's first OCR model.
"""
import argparse
import difflib
import html
import json
import time
from datetime import datetime
from pathlib import Path

import server
from evaluate_models import cer

ROOT = Path(__file__).resolve().parent
FINETUNED = 'typhoon-ocr-qlora-v1-rp1:latest'
PREVIOUS_DEFAULT = 'typhoon-ocr-finetuned:latest'  # v6 default (base weights)


def _reference(path: Path):
    stem = path.stem
    for suffix in ('-scan', '-digital'):
        stem = stem.removesuffix(suffix)
    ref = path.with_name(stem + '.txt')
    return ref.read_text(encoding='utf-8') if ref.exists() and ref != path else None


def compare(files, models, references=None, runner=None):
    """One row per (file, model): {file, model, ok, text, seconds, cer, error}."""
    runner = runner or server.ocr_image
    rows = []
    for path in map(Path, files):
        data = path.read_bytes()
        ref = (references or {}).get(str(path), _reference(path))
        for model in models:
            started = time.perf_counter()
            row = {'file': str(path), 'model': model, 'ok': False, 'text': '', 'cer': None, 'error': None, 'route': None}
            try:
                text, route = server.parse_document(path.name, data, ocr_model=model,
                                                     ocr_runner=lambda image, m=model: runner(image, m))
                row.update(ok=True, text=text, route=route, cer=cer(ref, text) if ref is not None else None)
            except Exception as e:  # one model failing must not hide the other's result
                row['error'] = f'{type(e).__name__}: {e}'
            row['seconds'] = round(time.perf_counter() - started, 2)
            rows.append(row)
    return rows


def _diff_html(a, b):
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if op == 'equal':
            out.append(html.escape(b[j1:j2]))
        else:
            if i1 != i2:
                out.append(f'<del>{html.escape(a[i1:i2])}</del>')
            if j1 != j2:
                out.append(f'<ins>{html.escape(b[j1:j2])}</ins>')
    return ''.join(out)


def write_report(rows, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    models = list(dict.fromkeys(r['model'] for r in rows))
    by_file = {}
    for r in rows:
        by_file.setdefault(r['file'], {})[r['model']] = r
    parts = ['<!doctype html><meta charset="utf-8"><title>OCR comparison</title><style>'
             'body{font:14px system-ui;margin:24px;background:#fafaf7;color:#1b1b1b}'
             'table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{border:1px solid #ccc;padding:8px;vertical-align:top}'
             'pre{white-space:pre-wrap;font:13px ui-monospace,monospace;margin:0}del{background:#fdd}ins{background:#dfd;text-decoration:none}'
             '.err{color:#a00}</style>',
             f'<h1>OCR comparison</h1><p>{html.escape(datetime.now().isoformat(timespec="seconds"))} · '
             'Highlights in each later column show its differences from the first column '
             '(<del>removed</del>, <ins>added</ins>).</p>',
             '<table><tr><th>File</th>' + ''.join(f'<th>{html.escape(m)}</th>' for m in models) + '</tr>']
    for file, cells in by_file.items():
        first = cells.get(models[0], {}).get('text', '')
        parts.append(f'<tr><td>{html.escape(Path(file).name)}</td>')
        for i, m in enumerate(models):
            r = cells.get(m)
            if not r or not r['ok']:
                parts.append(f'<td class="err">{html.escape((r or {}).get("error") or "not run")}</td>')
                continue
            stats = f'{r["seconds"]} s' + (f' · CER {r["cer"]:.3%}' if r['cer'] is not None else '')
            stats += ' · ' + html.escape(r['route'] or '') + ('' if 'OCR' in (r['route'] or '') else ' (no OCR used: models cannot differ)')
            body = html.escape(r['text']) if i == 0 else _diff_html(first, r['text'])
            parts.append(f'<td><b>{stats}</b><pre>{body}</pre></td>')
        parts.append('</tr>')
    parts.append('</table>')
    out.write_text(''.join(parts), encoding='utf-8')
    return out


def _default_models():
    policy = json.loads((ROOT / 'model-policy.json').read_text(encoding='utf-8'))
    first = policy['ocr'][0]['name']
    return [PREVIOUS_DEFAULT, first] if first != PREVIOUS_DEFAULT else [first, FINETUNED]


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('files', nargs='+', type=Path)
    p.add_argument('--models', nargs='+')
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    rows = compare(a.files, a.models or _default_models())
    out = write_report(rows, a.out or ROOT.parent / 'compare-reports' / f'ocr-{datetime.now():%Y%m%d-%H%M%S}.html')
    for r in rows:
        print(f"{Path(r['file']).name:28} {r['model']:36} {'ok' if r['ok'] else 'FAIL'} {r['seconds']}s"
              + (f" cer={r['cer']:.4f}" if r['cer'] is not None else '') + (f" {r['error']}" if r['error'] else ''))
    print('report:', out)
