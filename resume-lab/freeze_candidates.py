"""Freeze development-qualified candidates before any held-out inference."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import server
from auto_policy import engine_fingerprint

ROOT=Path(__file__).resolve().parent
EXTRACTION_GATES={'success_rate':1.0,'identity_exact':.95,'skill_f1':.9,
                  'employment_education_exact':.85,'date_exact':.9,'record_precision':.95,'literal_evidence_rate':.95}


def qualifies(row, stage):
    if stage=='extraction':
        return all(row[k]>=threshold for k,threshold in EXTRACTION_GATES.items())
    return row['success_rate']==1 and row['cer']<=.05 and all(g['cer']<=.08 for g in row['by_language'].values())


def ordered(rows, stage):
    rows=[r for r in rows if qualifies(r,stage)]
    if stage=='extraction':
        keys=[k for k in EXTRACTION_GATES if k!='success_rate']
        score=lambda r: -sum(r[k] for k in keys)/len(keys)
    else:
        score=lambda r:r['cer']
    # Form tie groups relative to each group's best accuracy, not a rounding boundary.
    result=[]
    rows.sort(key=score)
    while rows:
        best=score(rows[0])
        tied=[r for r in rows if score(r)-best<=.001]
        result.extend(sorted(tied,key=lambda r:r['mean_seconds']))
        rows=[r for r in rows if r not in tied]
    return result


def main():
    path=ROOT/'evaluation/frozen-candidates.json'
    if path.exists():
        raise SystemExit('Candidates already frozen; do not overwrite after seeing holdout.')
    value={'status':'awaiting-holdout','created_at':datetime.now(timezone.utc).isoformat(),
           'engine_sha256':engine_fingerprint(server),'extraction_gates':EXTRACTION_GATES,
           'ocr_gates':{'success_rate':1,'cer_max':.05,'per_language_cer_max':.08},'evidence':{}}
    for stage,run in [('extraction','refined-extraction-v4'),('ocr','improved-ocr-v4')]:
        source=ROOT/'evaluation/runs'/run/'summary.json'
        report=json.loads(source.read_text())
        ranked=ordered(report['summary'],stage)
        if not ranked:
            raise SystemExit(f'No development-qualified {stage} candidate')
        inventory={m['name']:m for m in report['configuration']['models']}
        value[stage]=[{'name':r['model'],'digest':inventory[r['model']]['digest']} for r in ranked]
        value['evidence'][stage]={'run':run,'summary_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
    for name in ['corpus/manifest.json','development-labels-v2.json','SELECTION-PROTOCOL.md']:
        value['evidence'][name]=hashlib.sha256((ROOT/'evaluation'/name).read_bytes()).hexdigest()
    path.write_text(json.dumps(value,indent=2),encoding='utf-8')
    print(json.dumps(value,indent=2))


if __name__=='__main__':
    main()
