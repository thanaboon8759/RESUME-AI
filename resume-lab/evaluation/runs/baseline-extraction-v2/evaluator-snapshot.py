"""Live, resumable evaluation of installed models against a frozen corpus."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import server

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT/'evaluation/corpus'


def normalize(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', str(value or ''))).strip().casefold()


def cer(reference, actual):
    reference, actual = normalize(reference), normalize(actual)
    row = list(range(len(actual)+1))
    for i, a in enumerate(reference,1):
        next_row=[i]
        for j,b in enumerate(actual,1):
            next_row.append(min(row[j]+1,next_row[j-1]+1,row[j-1]+(a!=b)))
        row=next_row
    return row[-1]/max(1,len(reference))


def extraction_metrics(profile, truth, source):
    metrics={}
    fields=['full_name','contact_email','contact_phone']
    metrics['identity_exact']=sum(normalize(profile.get(k))==normalize(truth.get(k)) for k in fields)/len(fields)
    actual={normalize(s) for s in profile.get('skills',[])}
    expected={normalize(s) for s in truth['skills']}
    true=len(actual & expected)
    precision=true/len(actual) if actual else float(not expected)
    recall=true/len(expected) if expected else float(not actual)
    metrics.update(skill_precision=precision,skill_recall=recall,skill_f1=2*precision*recall/(precision+recall) if precision+recall else 0)
    matches=[]; date_matches=[]
    for collection,keys,anchor in [('experience',['company','role','start_date','end_date'],'company'),('education',['institution','degree','field_of_study','graduation_year'],'institution')]:
        for target in truth.get(collection,[]):
            candidate=next((e for e in profile.get(collection,[]) if normalize(e.get(anchor))==normalize(target.get(anchor))),{})
            for key in keys:
                if key not in target: continue
                same=normalize(candidate.get(key))==normalize(target.get(key))
                matches.append(same)
                if 'date' in key or 'year' in key: date_matches.append(same)
    metrics['employment_education_exact']=sum(matches)/len(matches) if matches else 1.0
    metrics['date_exact']=sum(date_matches)/len(date_matches) if date_matches else 1.0
    facts=[profile.get(k) for k in fields if profile.get(k)]+profile.get('skills',[])
    for collection in ['experience','education']:
        for entry in profile.get(collection,[]):
            facts.extend(v for k,v in entry.items() if isinstance(v,str) and v)
    unmatched=[fact for fact in facts if normalize(fact) not in normalize(source)]
    metrics['literal_evidence_rate']=1-len(unmatched)/len(facts) if facts else 0
    metrics['unmatched_facts']=unmatched
    return metrics


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--split',choices=['development','holdout'],default='development')
    parser.add_argument('--stage',choices=['extraction','ocr'],required=True)
    parser.add_argument('--run',required=True,help='Unique run identifier; an identical interrupted run resumes.')
    parser.add_argument('--models',nargs='+')
    args=parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',args.run): parser.error('run must be a simple identifier')
    manifest_bytes=(CORPUS/'manifest.json').read_bytes()
    manifest=json.loads(manifest_bytes)
    samples=[s for s in manifest['samples'] if s['split']==args.split]
    inventory=server.ollama('/api/tags')['models']
    capability='completion' if args.stage=='extraction' else 'vision'
    models=[m for m in inventory if capability in m.get('capabilities',[]) and (not args.models or m['name'] in args.models)]
    if not models: parser.error('No eligible installed models')
    if args.models and set(args.models)!={m['name'] for m in models}: parser.error('Requested model missing or incompatible')
    directory=ROOT/'evaluation/runs'/args.run
    directory.mkdir(parents=True,exist_ok=True)
    config={'stage':args.stage,'split':args.split,'corpus_sha256':hashlib.sha256(manifest_bytes).hexdigest(),
            'server_sha256':hashlib.sha256((ROOT/'server.py').read_bytes()).hexdigest(),
            'evaluator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'models':[{k:m[k] for k in ['name','digest','details','capabilities']} for m in models]}
    config_path=directory/'configuration.json'
    if config_path.exists() and json.loads(config_path.read_text())!=config:
        raise SystemExit('Configuration changed: choose a new run identifier.')
    config_path.write_text(json.dumps(config,indent=2),encoding='utf-8')
    (directory/'inventory.json').write_text(json.dumps({'models':inventory,'ollama':server.ollama('/api/version'),'platform':platform.platform()},indent=2),encoding='utf-8')
    records_path=directory/'attempts.jsonl'
    previous=[json.loads(line) for line in records_path.read_text(encoding='utf-8').splitlines()] if records_path.exists() else []
    finished={(r['model'],r['sample_id']) for r in previous}
    original=server.ollama
    for model in models:
        for sample in samples:
            if (model['name'],sample['id']) in finished: continue
            responses=[]
            def captured(path,payload=None):
                response=original(path,payload)
                if payload is not None: responses.append(response)
                return response
            server.ollama=captured
            record={'model':model['name'],'digest':model['digest'],'sample_id':sample['id'],
                    'language':sample['language'],'started_at':datetime.now(timezone.utc).isoformat()}
            print(f"RUN {args.stage} {model['name']} {sample['id']}",flush=True)
            started=time.perf_counter()
            try:
                kind='text' if args.stage=='extraction' else 'image'
                filename=sample['files'][kind]
                content=(CORPUS/filename).read_bytes()
                if hashlib.sha256(content).hexdigest()!=sample['sha256'][kind]: raise ValueError('Corpus file changed')
                result=server.scan(filename,content,model=model['name'] if args.stage=='extraction' else '',
                                   ocr_model=model['name'] if args.stage=='ocr' else '',parse_only=args.stage=='ocr')
                metrics=extraction_metrics(result['profile'],sample['truth'],sample['text']) if args.stage=='extraction' else {'cer':cer(sample['text'],result['source_text'])}
                record.update(status='ok',metrics=metrics,result=result)
            except Exception as exc:
                record.update(status='error',error=str(exc),metrics={})
            finally:
                server.ollama=original
            record.update(elapsed_seconds=time.perf_counter()-started,raw_responses=responses)
            with records_path.open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(record,ensure_ascii=False)+'\n');stream.flush()
            previous.append(record)
            print(f"DONE {record['status']} {record['elapsed_seconds']:.2f}s",flush=True)
    summary=[]
    for model in models:
        rows=[r for r in previous if r['model']==model['name']]
        count=len(rows); times=sorted(r['elapsed_seconds'] for r in rows)
        item={'model':model['name'],'attempts':count,'success_rate':sum(r['status']=='ok' for r in rows)/count,
              'mean_seconds':sum(times)/count,'observed_p95_seconds':times[math.ceil(.95*count)-1]}
        names=['identity_exact','skill_precision','skill_recall','skill_f1','employment_education_exact','date_exact','literal_evidence_rate'] if args.stage=='extraction' else ['cer']
        for metric in names:
            item[metric]=sum(r['metrics'].get(metric,1.0 if metric=='cer' else 0.0) for r in rows)/count
        summary.append(item)
    (directory/'summary.json').write_text(json.dumps({'configuration':config,'summary':summary,
        'limitations':['Synthetic pilot corpus, not population-wide accuracy.','Literal evidence is not semantic factuality.','OCR error attempts receive CER=1; character insertion errors can exceed 1.','Observed p95 is unstable with small samples.','Latency/token counts are cost proxies; no energy or monetary cost measured.']},indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    main()
