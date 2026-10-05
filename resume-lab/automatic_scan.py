"""Automatic upload pipeline; no user-selected model names are accepted."""
import time
from pathlib import Path

from auto_policy import PolicyError, attempt_stage, candidates, check_profile, engine_fingerprint, load_policy

POLICY_PATH=Path(__file__).resolve().parent/'model-policy.json'


def automatic_scan(engine,filename,data,parse_only=False,policy_path=POLICY_PATH):
    started=time.perf_counter()
    policy=None
    inventory=None
    pages=[]

    def context():
        nonlocal policy, inventory
        if policy is None:
            policy=load_policy(policy_path,expected_engine=engine_fingerprint(engine))
            inventory=engine.ollama('/api/tags').get('models',[])
        return policy,inventory

    def read_page(image):
        selection,tags=context()
        names=candidates(selection,tags,'ocr')
        value,model,attempts=attempt_stage(names,lambda name:engine.ocr_image(image,name),
                                          lambda _:None,(engine.ScanError,PolicyError))
        pages.append({'ocr_sequence':len(pages)+1,'model':model,'attempts':attempts})
        return value

    if not parse_only:
        selection,tags=context()
        extractors=candidates(selection,tags,'extraction')
    text,route=engine.parse_document(filename,data,ocr_runner=read_page)
    parsed=time.perf_counter()-started
    if parse_only:
        result={'profile':None,'schema_valid':None,'mode':'parse-only','model':None,
                'source_text':text,'warnings':[],'extraction_attempts':[]}
    else:
        result,model,attempts=attempt_stage(extractors,
            lambda name:engine.scan('extracted.txt',text.encode('utf-8'),model=name),
            check_profile,(engine.ScanError,PolicyError))
        result.update(model=model,extraction_attempts=attempts)
    models=list(dict.fromkeys(page['model'] for page in pages))
    result.update(filename=filename,route=route,ocr_used=bool(pages),ocr_model=', '.join(models) or None,
                  ocr_models=models,ocr_pages=pages,parse_seconds=round(parsed,3),
                  selection='automatic',policy_id=policy.get('id') if policy else None,
                  elapsed_seconds=round(time.perf_counter()-started,3))
    if pages:
        result['warnings'].append('OCR can change characters and dates. Compare the source text with the original document.')
    if any(a['status']=='error' for p in pages for a in p['attempts']) or any(a['status']=='error' for a in result['extraction_attempts']):
        result['warnings'].append('A validated fallback was used after an earlier attempt failed. See diagnostics for details.')
    return result


def selection_status(engine,policy_path=POLICY_PATH):
    policy=load_policy(policy_path,expected_engine=engine_fingerprint(engine))
    tags=engine.ollama('/api/tags').get('models',[])
    extraction=candidates(policy,tags,'extraction')
    try:
        ocr=candidates(policy,tags,'ocr')
        ocr_error=None
    except PolicyError as exc:
        ocr=[];ocr_error=str(exc)
    return {'ready':True,'policy_id':policy['id'],'extraction':extraction,'ocr':ocr,'ocr_error':ocr_error}
