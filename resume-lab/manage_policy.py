"""Freeze, then validate a model policy using immutable live evaluation runs."""
import argparse
import hashlib
import importlib.util
import inspect
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import server
from auto_policy import engine_fingerprint
from freeze_candidates import EXTRACTION_GATES, ordered, qualifies

ROOT=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def enforce_frozen_gates(frozen,protocol_hash):
    if frozen['protocol_sha256']!=protocol_hash or frozen['extraction_gates']!=EXTRACTION_GATES or frozen['ocr_gates']!={'success_rate':1,'cer_max':.05,'per_language_cer_max':.08}:
        raise ValueError('Frozen selection protocol or gates changed. Refusing promotion.')


def frozen_qualifies(row,stage,frozen):
    if stage=='extraction':
        return all(row[key]>=limit for key,limit in frozen['extraction_gates'].items())
    gates=frozen['ocr_gates']
    return row['success_rate']==gates['success_rate'] and row['cer']<=gates['cer_max'] and all(g['cer']<=gates['per_language_cer_max'] for g in row['by_language'].values())


def verify_scores(report,rows,samples,scorer,stage):
    metrics=['identity_exact','skill_precision','skill_recall','skill_f1','employment_education_exact','date_exact','record_precision','literal_evidence_rate'] if stage=='extraction' else ['cer']
    derived=[]
    for row in rows:
        sample=samples[row['sample_id']]
        result=row.get('result',{})
        if row['status']=='ok':
            values=scorer.extraction_metrics(result['profile'],sample['truth'],sample['text']) if stage=='extraction' else {'cer':scorer.cer(sample['text'],result['source_text'])}
        elif row['status']=='error':values={}
        else:raise ValueError('Unknown attempt status')
        derived.append({**row,'metrics':values})
    def check(group,summary):
        expected={'attempts':len(group),'success_rate':sum(r['status']=='ok' for r in group)/len(group),
                  **{k:sum(r['metrics'].get(k,1 if k=='cer' else 0) for r in group)/len(group) for k in metrics}}
        for key,value in expected.items():
            if key not in summary or not math.isclose(summary[key],value,rel_tol=1e-9,abs_tol=1e-9):
                raise ValueError('Summary does not match recorded results: '+key)
    for summary in report['summary']:
        group=[r for r in derived if r['model']==summary['model']]
        check(group,summary)
        if set(summary['by_language'])!={r['language'] for r in group}:raise ValueError('Language summary mismatch')
        for language,item in summary['by_language'].items():check([r for r in group if r['language']==language],item)
    return derived


def stage_contract(engine,stage):
    names=['ocr_image'] if stage=='ocr' else ['scan','atomic_skills']
    value={'functions':{n:inspect.getsource(getattr(engine,n)) for n in names}}
    if stage=='extraction':value.update(prompt=engine.SYSTEM_PROMPT,schema=engine.extraction_schema(),version=engine.PROMPT_VERSION)
    return value


def checked_report(run,stage,split,manifest_path):
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',run):raise ValueError('Invalid run identifier')
    directory=ROOT/'evaluation/runs'/run
    report_path=directory/'summary.json'
    report=json.loads(report_path.read_text())
    config=report['configuration']
    if config['stage']!=stage or config['split']!=split or config['corpus_sha256']!=sha(manifest_path):
        raise ValueError('Run stage/split/corpus mismatch')
    snapshot=directory/'server-snapshot.py'
    if sha(snapshot)!=config['server_sha256'] or sha(ROOT/'schemas/models.py')!=config['schema_sha256']:
        raise ValueError('Snapshot/schema integrity mismatch')
    evaluator=directory/'evaluator-snapshot.py'
    if sha(evaluator)!=config['evaluator_sha256'] or sha(ROOT/'evaluation/development-labels-v2.json')!=config['annotation_sha256']:
        raise ValueError('Evaluator snapshot or annotation provenance mismatch')
    if stage=='extraction' and (sha(ROOT/'source_facts.py')!=config['source_facts_sha256'] or sha(directory/'source-facts-snapshot.py')!=config['source_facts_sha256']):
        raise ValueError('Source repair implementation changed')
    spec=importlib.util.spec_from_file_location('checked_'+run,snapshot)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    if stage_contract(module,stage)!=stage_contract(server,stage):
        raise ValueError('Stage inference differs from the tested snapshot')
    samples={s['id']:s for s in json.loads(manifest_path.read_text(encoding='utf-8'))['samples'] if s['split']==split}
    attempts_path=directory/'attempts.jsonl'
    rows=[json.loads(line) for line in attempts_path.read_text(encoding='utf-8').splitlines()]
    expected={m['name'] for m in config['models']}
    if {r['model'] for r in rows}!=expected or {r['model'] for r in report['summary']}!=expected:
        raise ValueError('Report candidate set mismatch')
    for name in expected:
        group=[r for r in rows if r['model']==name]
        if len(group)!=len(samples) or {r['sample_id'] for r in group}!=set(samples):
            raise ValueError('Incomplete or duplicate attempts')
        expected_digest=next(m['digest'] for m in config['models'] if m['name']==name)
        if any(r['digest']!=expected_digest for r in group):raise ValueError('Attempt model digest mismatch')
    spec=importlib.util.spec_from_file_location('scorer_'+run,evaluator)
    scorer=importlib.util.module_from_spec(spec);sys.modules[spec.name]=scorer;spec.loader.exec_module(scorer)
    verify_scores(report,rows,samples,scorer,stage)
    return report,{'run':run,'summary_sha256':sha(report_path),'attempts_sha256':sha(attempts_path),
                   'stage_contract_sha256':hashlib.sha256(json.dumps(stage_contract(server,stage),sort_keys=True).encode()).hexdigest()}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['freeze','promote'])
    parser.add_argument('--id',required=True)
    parser.add_argument('--corpus',default='corpus-v2',choices=['corpus-v2'])
    parser.add_argument('--extraction',required=True)
    parser.add_argument('--ocr',required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',args.id):parser.error('Invalid policy identifier')
    manifest=ROOT/'evaluation'/args.corpus/'manifest.json'
    frozen_path=ROOT/'evaluation'/('frozen-candidates-'+args.id+'.json')
    if args.action=='freeze':
        if frozen_path.exists():raise SystemExit('Frozen record already exists; never overwrite it')
        value={'id':args.id,'status':'awaiting-holdout','created_at':datetime.now(timezone.utc).isoformat(),
               'engine_sha256':engine_fingerprint(server),'corpus_sha256':sha(manifest),'corpus_directory':args.corpus,
               'protocol_sha256':sha(ROOT/'evaluation/SELECTION-PROTOCOL.md'),'extraction_gates':EXTRACTION_GATES,
               'ocr_gates':{'success_rate':1,'cer_max':.05,'per_language_cer_max':.08},'development':{}}
        for stage,run in [('extraction',args.extraction),('ocr',args.ocr)]:
            report,evidence=checked_report(run,stage,'development',manifest)
            inventory={m['name']:m for m in report['configuration']['models']}
            ranked=ordered(report['summary'],stage)
            if not ranked:raise SystemExit('No qualified '+stage+' model')
            value[stage]=[{'name':r['model'],'digest':inventory[r['model']]['digest']} for r in ranked]
            value['development'][stage]=evidence
        frozen_path.write_text(json.dumps(value,indent=2),encoding='utf-8')
        print('Frozen:',frozen_path)
        return
    value=json.loads(frozen_path.read_text())
    enforce_frozen_gates(value,sha(ROOT/'evaluation/SELECTION-PROTOCOL.md'))
    if value['engine_sha256']!=engine_fingerprint(server) or value['corpus_sha256']!=sha(manifest):
        raise SystemExit('Frozen inference or corpus changed')
    holdout={};passing={}
    for stage,run in [('extraction',args.extraction),('ocr',args.ocr)]:
        report,evidence=checked_report(run,stage,'holdout',manifest)
        tested={m['name']:m['digest'] for m in report['configuration']['models']}
        if tested!={m['name']:m['digest'] for m in value[stage]}:raise SystemExit('Holdout candidates differ from frozen order/set')
        qualified={r['model'] for r in report['summary'] if frozen_qualifies(r,stage,value)}
        passing[stage]=[m for m in value[stage] if m['name'] in qualified]
        holdout[stage]=evidence
    decision={'policy_id':args.id,'passing':passing,'holdout':holdout,'approved':all(passing.values())}
    (ROOT/'evaluation'/('promotion-'+args.id+'.json')).write_text(json.dumps(decision,indent=2),encoding='utf-8')
    if not decision['approved']:raise SystemExit('Held-out gates failed. No policy promoted.')
    value.update(passing,status='validated',holdout=holdout,validated_at=datetime.now(timezone.utc).isoformat())
    policy_path=ROOT/'model-policy.json'
    if policy_path.exists():
        previous=json.loads(policy_path.read_text())
        if {k:v for k,v in previous.items() if k!='validated_at'}=={k:v for k,v in value.items() if k!='validated_at'}:
            print('Existing identical policy revalidated; preserving its timestamp and hash.')
            return
    policy_path.write_text(json.dumps(value,indent=2),encoding='utf-8')
    print('Validated model-policy.json:',json.dumps(passing))


if __name__=='__main__':main()
