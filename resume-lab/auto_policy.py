"""Digest-pinned selection and bounded fallback for evaluated local models."""
from __future__ import annotations

import json
import hashlib
import inspect
import re
import time
import unicodedata
from pathlib import Path


class PolicyError(Exception):
    pass


def valid_digest(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def stage_entries(policy, stage):
    if not isinstance(policy, dict) or stage not in {'ocr','extraction'}:
        raise PolicyError('Invalid automatic model policy.')
    entries = policy.get(stage)
    if not isinstance(entries, list) or not entries:
        raise PolicyError(f'No validated {stage} policy entries.')
    names = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('name'), str) or not entry['name'].strip() or not valid_digest(entry.get('digest')) or entry['name'] in names:
            raise PolicyError(f'Invalid or duplicate {stage} model policy entry.')
        names.add(entry['name'])
    return entries


def engine_fingerprint(engine):
    contract = {'prompt':engine.SYSTEM_PROMPT, 'schema':engine.extraction_schema(),
                'prompt_version':engine.PROMPT_VERSION,
                'source_facts_sha256':hashlib.sha256(Path(inspect.getfile(engine.refine)).read_bytes()).hexdigest(),
                'functions':{name:inspect.getsource(getattr(engine,name)) for name in ['scan','ocr_image','atomic_skills','refine','parse_document']}}
    return hashlib.sha256(json.dumps(contract,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()


def load_policy(path: Path, expected_engine=None):
    try:
        policy = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise PolicyError('Automatic model selection is not configured. Complete the local evaluation first.') from exc
    if not isinstance(policy, dict) or policy.get('status') != 'validated':
        raise PolicyError('Automatic model selection is awaiting held-out validation.')
    for stage in ['extraction','ocr']:
        stage_entries(policy, stage)
    if not valid_digest(policy.get('engine_sha256')) or (expected_engine is not None and policy['engine_sha256'] != expected_engine):
        raise PolicyError('Extraction/OCR configuration changed since evaluation. Revalidate the model policy.')
    return policy


def candidates(policy, inventory, stage):
    """Never silently promote an unknown model or a changed model digest."""
    capability = 'vision' if stage == 'ocr' else 'completion'
    if not isinstance(inventory, list):
        raise PolicyError('Local model inventory is invalid.')
    installed = {m['name']: m for m in inventory if isinstance(m,dict) and isinstance(m.get('name'),str) and valid_digest(m.get('digest'))}
    eligible = []
    for expected in stage_entries(policy, stage):
        actual = installed.get(expected['name'])
        if actual and actual.get('digest') == expected['digest'] and capability in actual.get('capabilities', []):
            eligible.append(expected['name'])
    if not eligible:
        raise PolicyError(f'No validated {stage} model is installed with its tested digest. Restore an evaluated model or rerun evaluation.')
    return eligible


def normalized(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', text)).strip().casefold()


def check_profile(result):
    """Reject empty profiles and unsupported contact/name facts; never manufacture replacements."""
    profile = result.get('profile')
    if not result.get('schema_valid') or not isinstance(profile, dict):
        raise PolicyError('Extraction did not return a valid profile.')
    source = normalized(result['source_text'])
    facts = [profile.get(k) for k in ['full_name','contact_email','contact_phone'] if profile.get(k)]
    for fact in facts:
        if normalized(fact) not in source:
            raise PolicyError('Extracted identity or contact information is not supported by the source.')
    if not any(profile.get(k) for k in ['full_name','skills','experience','education']):
        raise PolicyError('Extraction returned an empty profile.')


def attempt_stage(names, call, validate, recoverable_errors):
    """Try each validated configuration at most once; keep explicit failure provenance."""
    attempts = []
    for name in names:
        started = time.perf_counter()
        try:
            result = call(name)
            validate(result)
        except recoverable_errors as exc:
            attempts.append({'model': name, 'status': 'error', 'error': str(exc),
                             'elapsed_seconds': round(time.perf_counter()-started,3)})
            continue
        attempts.append({'model': name, 'status': 'ok', 'elapsed_seconds': round(time.perf_counter()-started,3)})
        return result, name, attempts
    detail = '; '.join(f"{a['model']}: {a['error']}" for a in attempts)
    raise PolicyError('All validated models failed. No successful result was created. '+detail)
