"""Live, resumable evaluation of installed models against a frozen corpus."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import server

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT/'evaluation/corpus'
LABELS = ROOT/'evaluation/development-labels-v2.json'


def annotated_samples(manifest):
    if manifest.get('annotations_frozen') is True:
        return json.loads(json.dumps(manifest['samples']))
    overlay = json.loads(LABELS.read_text(encoding='utf-8'))
    if overlay['source_manifest_sha256'] != hashlib.sha256((CORPUS/'manifest.json').read_bytes()).hexdigest():
        raise ValueError('Annotation overlay does not match the frozen corpus.')
    corrections = overlay['changes']
    samples = json.loads(json.dumps(manifest['samples']))
    for sample in samples:
        if sample['split'] == 'development':
            sample['truth'].update(corrections.get(sample['id'], {}))
    return samples


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
    expected_records=0; predicted_records=0; matched_records=0
    for collection,keys,anchor in [('experience',['company','role','start_date','end_date'],'company'),('education',['institution','degree','field_of_study','graduation_year'],'institution')]:
        expected_records+=len(truth.get(collection,[]))
        predicted_records+=len(profile.get(collection,[]))
        remaining=list(profile.get(collection,[]))
        for target in truth.get(collection,[]):
            choices=[(index,entry) for index,entry in enumerate(remaining) if normalize(entry.get(anchor))==normalize(target.get(anchor))]
            if choices:
                index,candidate=max(choices,key=lambda pair:sum(normalize(pair[1].get(key))==normalize(target.get(key)) for key in keys))
                remaining.pop(index)
                matched_records+=1
            else:
                candidate={}
            for key in keys:
                if key not in target: continue
                same=normalize(candidate.get(key))==normalize(target.get(key))
                matches.append(same)
                if 'date' in key or 'year' in key: date_matches.append(same)
    metrics['employment_education_exact']=sum(matches)/len(matches) if matches else 1.0
    metrics['date_exact']=sum(date_matches)/len(date_matches) if date_matches else 1.0
    metrics['record_precision']=matched_records/predicted_records if predicted_records else float(not expected_records)
    facts=[profile.get(k) for k in fields if profile.get(k)]+profile.get('skills',[])
    for collection in ['experience','education']:
        for entry in profile.get(collection,[]):
            facts.extend(v for k,v in entry.items() if isinstance(v,str) and v)
            facts.extend(entry.get('achievements',[]))
    unmatched=[fact for fact in facts if normalize(fact) not in normalize(source)]
    metrics['literal_evidence_rate']=1-len(unmatched)/len(facts) if facts else 0
    metrics['unmatched_facts']=unmatched
    return metrics


def read_records(path):
    """Recover only a torn final append; never silently discard completed records."""
    if not path.exists(): return []
    content=path.read_bytes()
    lines=content.splitlines(keepends=True)
    records=[]; valid_bytes=0
    for index,line in enumerate(lines):
        try:
            record=json.loads(line)
        except (json.JSONDecodeError,UnicodeDecodeError):
            if index!=len(lines)-1 or line.endswith(b'\n'): raise
            path.with_suffix('.incomplete').write_bytes(line)
            with path.open('r+b') as stream: stream.truncate(valid_bytes)
            break
        records.append(record);valid_bytes+=len(line)
    keys=[(r['model'],r['sample_id']) for r in records]
    if len(keys)!=len(set(keys)): raise ValueError('Duplicate completed records in run')
    # A complete JSON record interrupted just before its newline is still valid.
    if records and valid_bytes==len(content) and not content.endswith(b'\n'):
        with path.open('ab') as stream: stream.write(b'\n')
    return records


def main():
    global CORPUS
    parser=argparse.ArgumentParser()
    parser.add_argument('--split',choices=['development','holdout'],default='development')
    parser.add_argument('--stage',choices=['extraction','ocr'],required=True)
    parser.add_argument('--run',required=True,help='Unique run identifier; an identical interrupted run resumes.')
    parser.add_argument('--models',nargs='+')
    parser.add_argument('--corpus',default='corpus',choices=['corpus','corpus-v2'])
    args=parser.parse_args()
    CORPUS=ROOT/'evaluation'/args.corpus
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',args.run): parser.error('run must be a simple identifier')
    manifest_bytes=(CORPUS/'manifest.json').read_bytes()
    manifest=json.loads(manifest_bytes)
    samples=[s for s in annotated_samples(manifest) if s['split']==args.split]
    inventory=server.ollama('/api/tags')['models']
    capability='completion' if args.stage=='extraction' else 'vision'
    models=sorted([m for m in inventory if capability in m.get('capabilities',[]) and (not args.models or m['name'] in args.models)],key=lambda m:m['name'])
    if not models: parser.error('No eligible installed models')
    if args.models and set(args.models)!={m['name'] for m in models}: parser.error('Requested model missing or incompatible')
    directory=ROOT/'evaluation/runs'/args.run
    directory.mkdir(parents=True,exist_ok=True)
    config={'stage':args.stage,'split':args.split,'corpus_sha256':hashlib.sha256(manifest_bytes).hexdigest(),
            'corpus_directory':args.corpus,
            'annotation_sha256':hashlib.sha256(LABELS.read_bytes()).hexdigest(),
            'server_sha256':hashlib.sha256((ROOT/'server.py').read_bytes()).hexdigest(),
            'schema_sha256':hashlib.sha256((ROOT/'schemas/models.py').read_bytes()).hexdigest(),
            'source_facts_sha256':hashlib.sha256((ROOT/'source_facts.py').read_bytes()).hexdigest(),
            'runtime':{'ollama':server.ollama('/api/version'),'platform':platform.platform()},
            'evaluator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'models':[{k:m[k] for k in ['name','digest','details','capabilities']} for m in models]}
    config_path=directory/'configuration.json'
    if config_path.exists() and json.loads(config_path.read_text())!=config:
        raise SystemExit('Configuration changed: choose a new run identifier.')
    config_path.write_text(json.dumps(config,indent=2),encoding='utf-8')
    for name, source in [('server-snapshot.py',ROOT/'server.py'),('evaluator-snapshot.py',Path(__file__)),('schema-snapshot.py',ROOT/'schemas/models.py'),('source-facts-snapshot.py',ROOT/'source_facts.py')]:
        (directory/name).write_bytes(source.read_bytes())
    (directory/'inventory.json').write_text(json.dumps({'models':inventory,'ollama':server.ollama('/api/version'),'platform':platform.platform()},indent=2),encoding='utf-8')
    records_path=directory/'attempts.jsonl'
    previous=read_records(records_path)
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
                inference_elapsed=time.perf_counter()-started
                scoring_started=time.perf_counter()
                metrics=extraction_metrics(result['profile'],sample['truth'],sample['text']) if args.stage=='extraction' else {'cer':cer(sample['text'],result['source_text'])}
                record.update(status='ok',metrics=metrics,result=result,elapsed_seconds=inference_elapsed,scoring_seconds=time.perf_counter()-scoring_started)
            except Exception as exc:
                record.update(status='error',error=str(exc),metrics={})
            finally:
                server.ollama=original
            record.setdefault('elapsed_seconds',time.perf_counter()-started)
            record['raw_responses']=responses
            try:
                record['loaded_models_after_scan']=original('/api/ps').get('models',[])
            except server.ScanError as exc:
                record['resource_observation_error']=str(exc)
            with records_path.open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(record,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno())
            previous.append(record)
            print(f"DONE {record['status']} {record['elapsed_seconds']:.2f}s",flush=True)
    summary=[]
    for model in models:
        rows=[r for r in previous if r['model']==model['name']]
        count=len(rows); times=sorted(r['elapsed_seconds'] for r in rows)
        item={'model':model['name'],'attempts':count,'success_rate':sum(r['status']=='ok' for r in rows)/count,
              'mean_seconds':sum(times)/count,'observed_p95_seconds':times[math.ceil(.95*count)-1]}
        names=['identity_exact','skill_precision','skill_recall','skill_f1','employment_education_exact','date_exact','record_precision','literal_evidence_rate'] if args.stage=='extraction' else ['cer']
        for metric in names:
            item[metric]=sum(r['metrics'].get(metric,1.0 if metric=='cer' else 0.0) for r in rows)/count
        item['by_language']={}
        for language in sorted({r['language'] for r in rows}):
            group=[r for r in rows if r['language']==language]
            item['by_language'][language]={'attempts':len(group),'success_rate':sum(r['status']=='ok' for r in group)/len(group),
                **{metric:sum(r['metrics'].get(metric,1.0 if metric=='cer' else 0.0) for r in group)/len(group) for metric in names}}
        summary.append(item)
    (directory/'summary.json').write_text(json.dumps({'configuration':config,'summary':summary,
        'limitations':['Synthetic pilot corpus, not population-wide accuracy.','Literal evidence is not semantic factuality.','OCR error attempts receive CER=1; character insertion errors can exceed 1.','Observed p95 is unstable with small samples.','Latency/token counts are cost proxies; no energy or monetary cost measured.']},indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    main()
