"""Derive corrected-label scores from immutable saved responses; no inference."""
import hashlib
import json
from pathlib import Path

from evaluate_models import annotated_samples, extraction_metrics

ROOT = Path(__file__).resolve().parent


def main():
    manifest = ROOT/'evaluation/corpus/manifest.json'
    labels = ROOT/'evaluation/development-labels-v2.json'
    samples = {s['id']: s for s in annotated_samples(json.loads(manifest.read_text(encoding='utf-8')))}
    reports = []
    for directory in sorted((ROOT/'evaluation/runs').iterdir()):
        config_path = directory/'configuration.json'
        if not config_path.exists() or not (directory/'summary.json').exists():
            continue
        config = json.loads(config_path.read_text())
        if config['stage'] != 'extraction' or config['split'] != 'development':
            continue
        if config['corpus_sha256'] != hashlib.sha256(manifest.read_bytes()).hexdigest():
            raise ValueError(f'Historical run {directory.name} used a different corpus.')
        path = directory/'attempts.jsonl'
        rows = []
        for line in path.read_bytes().splitlines():
            original = json.loads(line)
            sample = samples[original['sample_id']]
            metrics = extraction_metrics(original['result']['profile'], sample['truth'], sample['text']) if original['status'] == 'ok' else {}
            rows.append({'model': original['model'], 'sample_id': sample['id'], 'status': original['status'],
                         'elapsed_seconds': original['elapsed_seconds'], 'metrics': metrics,
                         'source_record_sha256': hashlib.sha256(line).hexdigest()})
        summary = []
        for model in sorted({r['model'] for r in rows}):
            group = [r for r in rows if r['model'] == model]
            keys = ['identity_exact','skill_f1','employment_education_exact','date_exact','record_precision','literal_evidence_rate']
            summary.append({'model': model, 'attempts': len(group), 'success_rate': sum(r['status']=='ok' for r in group)/len(group),
                            **{k: sum(r['metrics'].get(k,0) for r in group)/len(group) for k in keys}})
        reports.append({'original_run': directory.name, 'original_configuration': config,
                        'source_attempts_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'rows': rows, 'summary': summary})
    output = {'purpose': 'Corrected development labels only; original responses, timing and failures retained. Not a held-out result.',
              'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
              'annotation_sha256': hashlib.sha256(labels.read_bytes()).hexdigest(),
              'scorer_sha256': hashlib.sha256((ROOT/'evaluate_models.py').read_bytes()).hexdigest(), 'runs': reports}
    destination = ROOT/'evaluation/corrected-development-scores.json'
    destination.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{k:r[k] for k in ['original_run','summary']} for r in reports],indent=2))


if __name__ == '__main__':
    main()
