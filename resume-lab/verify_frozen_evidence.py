"""Check stage-specific development snapshots against the already-frozen engine."""
import hashlib
import importlib.util
import inspect
import json
import sys
from pathlib import Path

import server
from auto_policy import engine_fingerprint

ROOT=Path(__file__).resolve().parent


def stage_fingerprint(engine,stage):
    names=['ocr_image'] if stage=='ocr' else ['scan','atomic_skills']
    value={'functions':{n:inspect.getsource(getattr(engine,n)) for n in names}}
    if stage=='extraction':
        value.update(prompt=engine.SYSTEM_PROMPT,schema=engine.extraction_schema(),version=engine.PROMPT_VERSION)
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def verify():
    frozen=json.loads((ROOT/'evaluation/frozen-candidates.json').read_text())
    if frozen['engine_sha256']!=engine_fingerprint(server):
        raise ValueError('Current engine differs from the frozen candidate configuration')
    checks={}
    for stage in ['extraction','ocr']:
        evidence=frozen['evidence'][stage]
        directory=ROOT/'evaluation/runs'/evidence['run']
        report_path=directory/'summary.json'
        if hashlib.sha256(report_path.read_bytes()).hexdigest()!=evidence['summary_sha256']:
            raise ValueError('Development summary changed')
        report=json.loads(report_path.read_text())
        snapshot=directory/'server-snapshot.py'
        if report['configuration']['stage']!=stage or report['configuration']['split']!='development':
            raise ValueError('Wrong evidence stage/split')
        if hashlib.sha256(snapshot.read_bytes()).hexdigest()!=report['configuration']['server_sha256']:
            raise ValueError('Development snapshot changed')
        spec=importlib.util.spec_from_file_location('evaluated_'+stage,snapshot)
        module=importlib.util.module_from_spec(spec)
        sys.modules[spec.name]=module
        spec.loader.exec_module(module)
        tested=stage_fingerprint(module,stage)
        if tested!=stage_fingerprint(server,stage):
            raise ValueError(f'{stage} inference differs from the tested development configuration')
        checks[stage]={'run':evidence['run'],'stage_fingerprint':tested,'matches':True}
    (ROOT/'evaluation/frozen-evidence-verification.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    return checks


if __name__=='__main__':
    print(json.dumps(verify(),indent=2))
