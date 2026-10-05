"""Exercise the actual token-protected upload endpoint over all held-out formats."""
import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from evaluate_models import cer, extraction_metrics

ROOT=Path(__file__).resolve().parent
BASE='http://127.0.0.1:8765'
DEST=ROOT/'evaluation/upload-verification-v6'


def request(path,payload=None,token=''):
    req=urllib.request.Request(BASE+path,data=json.dumps(payload).encode() if payload is not None else None,
                               headers={'Content-Type':'application/json','X-Lab-Token':token,'Origin':BASE})
    with urllib.request.urlopen(req,timeout=600) as response:return json.load(response)


def main():
    corpus=ROOT/'evaluation/corpus-v2'
    manifest_path=corpus/'manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    samples=[s for s in manifest['samples'] if s['split']=='holdout']
    DEST.mkdir(exist_ok=True)
    config={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['server.py','automatic_scan.py','auto_policy.py','source_facts.py','model-policy.json','evaluation/corpus-v2/manifest.json']}
    config_path=DEST/'configuration.json'
    if config_path.exists() and json.loads(config_path.read_text())!=config:raise SystemExit('Verification configuration changed')
    config_path.write_text(json.dumps(config,indent=2))
    output=DEST/'attempts.jsonl'
    records=[json.loads(line) for line in output.read_text(encoding='utf-8').splitlines()] if output.exists() else []
    completed={(r['sample_id'],r['format']) for r in records}
    token=request('/api/session')['token']
    for kind in ['text','digital_pdf','image','scanned_pdf']:
        for sample in samples:
            if (sample['id'],kind) in completed:continue
            filename=sample['files'][kind]
            data=(corpus/filename).read_bytes()
            if hashlib.sha256(data).hexdigest()!=sample['sha256'][kind]:raise ValueError('Input changed')
            record={'sample_id':sample['id'],'language':sample['language'],'format':kind}
            print('UPLOAD',kind,sample['id'],flush=True)
            started=time.perf_counter()
            try:
                result=request('/api/scan',{'filename':filename,'data':base64.b64encode(data).decode()},token)
                assert result['selection']=='automatic' and result['profile'] is not None
                assert result['ocr_used']==(kind in ['image','scanned_pdf'])
                metrics=extraction_metrics(result['profile'],sample['truth'],sample['text'])
                metrics['source_cer']=cer(sample['text'],result['source_text'])
                record.update(status='ok',result=result,metrics=metrics)
            except urllib.error.HTTPError as exc:
                record.update(status='error',error=exc.read().decode(),metrics={})
            except Exception as exc:
                record.update(status='error',error=str(exc),metrics={})
            record['elapsed_seconds']=time.perf_counter()-started
            with output.open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(record,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno())
            records.append(record)
            print(record['status'],round(record['elapsed_seconds'],2),flush=True)
    summary=[]
    for kind in ['text','digital_pdf','image','scanned_pdf']:
        rows=[r for r in records if r['format']==kind]
        keys=['identity_exact','skill_f1','employment_education_exact','date_exact','record_precision','literal_evidence_rate','source_cer']
        summary.append({'format':kind,'attempts':len(rows),'success_rate':sum(r['status']=='ok' for r in rows)/len(rows),
                        **{k:sum(r['metrics'].get(k,1 if k=='source_cer' else 0) for r in rows)/len(rows) for k in keys},
                        'mean_seconds':sum(r['elapsed_seconds'] for r in rows)/len(rows)})
    (DEST/'summary.json').write_text(json.dumps({'configuration':config,'summary':summary},indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
