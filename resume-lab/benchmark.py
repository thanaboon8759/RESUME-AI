"""Live smoke comparison; never promotes a production winner from this small corpus."""
import argparse
import hashlib
import json
import math
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

from server import ollama, scan

ROOT = Path(__file__).resolve().parent


def score(result, truth):
    profile = result['profile']
    actual = {value.strip().casefold() for value in profile['skills']}
    expected = {value.strip().casefold() for value in truth['skills']}
    common = len(actual & expected)
    precision = common / len(actual) if actual else 0
    recall = common / len(expected) if expected else 0
    return {
        'skill_precision': precision, 'skill_recall': recall,
        'skill_f1': 2 * precision * recall / (precision + recall) if precision + recall else 0,
        'contact_exact_match': sum(profile.get(key) == truth.get(key) for key in ('full_name', 'contact_email', 'contact_phone')) / 3,
        'unmatched_literal_skills': [entry['skill'] for entry in result['skill_evidence'] if not entry['literal_match']],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--models', nargs='+', default=['qwen2.5:7b','llama3.1:8b','deepseek-r1:8b'])
    parser.add_argument('--limit', type=int, default=3)
    parser.add_argument('--repeat', type=int, default=1)
    parser.add_argument('--output', default='live-benchmark.json')
    args = parser.parse_args()
    if not 1 <= args.limit <= 20 or not 1 <= args.repeat <= 3:
        parser.error('limit must be 1..20 and repeat 1..3')
    fixture_data = (ROOT / 'benchmark-fixtures.json').read_bytes()
    fixtures = json.loads(fixture_data)[:args.limit]
    installed = {entry['name']: entry for entry in ollama('/api/tags')['models']}
    if any(model not in installed for model in args.models):
        parser.error('Every selected model must already be installed.')
    report = {'mode':'live', 'started_at':datetime.now(timezone.utc).isoformat(),
              'dataset_sha256':hashlib.sha256(fixture_data).hexdigest(),
              'code_sha256':hashlib.sha256((ROOT/'server.py').read_bytes()).hexdigest(),
              'platform':platform.platform(), 'models':[installed[model] for model in args.models],
              'ollama_version':ollama('/api/version'),
              'limits':{'samples':len(fixtures),'repeats':args.repeat,'temperature':0,'num_ctx':32768,'num_predict':4096},
              'production_winner':None, 'records':[], 'summary':[],
              'limitations':['Repository fixtures are development data, not a sealed holdout.',
                             'Exact skill labels omit some skills stated elsewhere in resumes; inspect disagreements.',
                             'Exact full-name scoring may penalize preservation of a bilingual name.',
                             'Literal skill matches are a diagnostic, not a factual hallucination rate.',
                             'No dollar or energy cost is measured; latency and token counts are resource proxies.']}
    output = ROOT / args.output
    for model in args.models:
        for repeat in range(args.repeat):
            for sample in fixtures:
                print(f"RUN {model} {sample['id']} repeat={repeat+1}", flush=True)
                started = time.perf_counter()
                record = {'model':model,'sample_id':sample['id'],'repeat':repeat+1}
                try:
                    result = scan(sample['id']+'.md',sample['markdown'].encode(),model=model)
                    record.update(status='ok',result=result,metrics=score(result,sample['ground_truth']))
                except Exception as exc:
                    record.update(status='error',error=str(exc),metrics={'skill_f1':0,'contact_exact_match':0})
                record['elapsed_seconds'] = time.perf_counter()-started
                report['records'].append(record)
                output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                print(f"DONE {record['status']} {record['elapsed_seconds']:.2f}s",flush=True)
        records = [entry for entry in report['records'] if entry['model']==model]
        durations = sorted(entry['elapsed_seconds'] for entry in records)
        report['summary'].append({'model':model,'attempts':len(records),
            'success_rate':sum(entry['status']=='ok' for entry in records)/len(records),
            'all_attempt_skill_f1':sum(entry['metrics']['skill_f1'] for entry in records)/len(records),
            'contact_exact_match':sum(entry['metrics']['contact_exact_match'] for entry in records)/len(records),
            'mean_seconds':sum(durations)/len(durations),'p95_seconds':durations[math.ceil(.95*len(durations))-1]})
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report['summary'],indent=2),flush=True)


if __name__ == '__main__':
    main()
