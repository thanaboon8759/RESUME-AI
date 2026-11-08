"""Seeded OCR training set and fresh corpus-v3 holdout, disjoint from the frozen evaluation corpus.

Renders with build_corpus_v2.render so training images look exactly like evaluation images.
Usage: python resume-lab/build_training_set.py --train 240 --val 30 --holdout 27
"""
import argparse
import hashlib
import json
import random
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import build_corpus_v2 as v2

ROOT = Path(__file__).resolve().parent
EVAL_MANIFEST = ROOT / 'evaluation/corpus-v2/manifest.json'
LANGS = ['en', 'th', 'bi']

EN_FIRST = ['Avery', 'Blake', 'Cameron', 'Dakota', 'Emerson', 'Finley', 'Harper', 'Jamie', 'Kendall', 'Logan',
            'Morgan', 'Noel', 'Parker', 'Quinn', 'Reese', 'Rowan', 'Sage', 'Skyler', 'Tatum', 'Wren']
EN_LAST = ['Abbott', 'Barrett', 'Calloway', 'Dalton', 'Ellison', 'Fairbanks', 'Garland', 'Hollis', 'Iverson',
           'Kingsley', 'Langford', 'Merritt', 'Norwood', 'Prescott', 'Radcliffe', 'Sterling', 'Thornton', 'Whitaker']
TH_FIRST = ['กมล', 'จิราพร', 'ชนินทร์', 'ณัฐพล', 'ธนพร', 'นภัส', 'ปวีณา', 'พิมพ์ชนก', 'ภูริ', 'วรเมธ',
            'ศุภชัย', 'สิรินทร์', 'อนุชา', 'อัญชลี', 'เกียรติ', 'ธีรวัฒน์', 'มนัสนันท์', 'รัฐพล']
TH_LAST = ['ศรีสุข', 'บุญมา', 'แก้วประเสริฐ', 'ทองดี', 'รุ่งเรือง', 'สมบูรณ์ชัย', 'วงศ์ไทย', 'ใจดี',
           'มั่นคง', 'เพชรรัตน์', 'สุขสวัสดิ์', 'จันทร์เพ็ญ', 'ประเสริฐวงศ์', 'นาคสวัสดิ์']
TH_ROMAN = {'กมล': 'Kamol', 'จิราพร': 'Jiraporn', 'ชนินทร์': 'Chanin', 'ณัฐพล': 'Nattapol', 'ธนพร': 'Thanaporn',
            'นภัส': 'Napat', 'ปวีณา': 'Paweena', 'พิมพ์ชนก': 'Pimchanok', 'ภูริ': 'Phuri', 'วรเมธ': 'Woramet',
            'ศุภชัย': 'Supachai', 'สิรินทร์': 'Sirin', 'อนุชา': 'Anucha', 'อัญชลี': 'Anchalee', 'เกียรติ': 'Kiat',
            'ธีรวัฒน์': 'Teerawat', 'มนัสนันท์': 'Manatsanan', 'รัฐพล': 'Rattapol'}
SKILLS = ['Python', 'Java', 'Go', 'Rust', 'C#', 'Kotlin', 'TypeScript', 'JavaScript', 'SQL', 'PostgreSQL', 'MySQL',
          'Redis', 'Docker', 'Kubernetes', 'Linux', 'Git', 'AWS', 'Azure', 'React', 'Vue', 'FastAPI', 'Django',
          'Spring', 'Pandas', 'Excel', 'Power BI', 'Tableau', 'Terraform', 'GraphQL', 'Flutter']
EN_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
EN_MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
                  'November', 'December']
TH_MONTHS = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
EN_COMPANIES = ['Northwind Labs', 'Bluegate Systems', 'Copperline Tech', 'Summit Data Works', 'Harbor Analytics',
                'Ironleaf Software', 'Maplewood Digital', 'Silverpine Cloud']
TH_COMPANIES = ['บริษัท นวัตกรรมดิจิทัล', 'บริษัท ข้อมูลก้าวหน้า', 'บริษัท ระบบอัจฉริยะ', 'บริษัท ซอฟต์แวร์สยาม',
                'บริษัท คลาวด์ไทย', 'บริษัท เทคโนโลยีรุ่งโรจน์']


def _eval_names():
    return {s['truth']['full_name'] for s in json.loads(EVAL_MANIFEST.read_text(encoding='utf-8'))['samples']}


def _name(rng, language):
    if language == 'en':
        return rng.choice(EN_FIRST) + ' ' + rng.choice(EN_LAST)
    first, last = rng.choice(TH_FIRST), rng.choice(TH_LAST)
    return first + ' ' + last if language == 'th' else f'{first} {last} ({TH_ROMAN[first]} {rng.choice(EN_LAST)})'


def _dates(rng, thai):
    start = rng.randint(2012, 2021)
    end = rng.choice([None, rng.randint(start + 1, 2025)])
    style = rng.randrange(4)
    if thai:
        be = lambda y: str(y + 543)
        if style % 2:
            return f'{rng.choice(TH_MONTHS)} {be(start)}', 'ปัจจุบัน' if end is None else f'{rng.choice(TH_MONTHS)} {be(end)}'
        return be(start), 'ปัจจุบัน' if end is None else be(end)
    now = rng.choice(['Present', 'Current'])
    if style == 0:
        return str(start), now if end is None else str(end)
    if style == 1:
        return f'{rng.choice(EN_MONTHS)} {start}', now if end is None else f'{rng.choice(EN_MONTHS)} {end}'
    if style == 2:
        return f'{rng.randint(1, 12):02d}/{start}', now if end is None else f'{rng.randint(1, 12):02d}/{end}'
    return f'{rng.choice(EN_MONTHS_LONG)} {start}', now if end is None else f'{rng.choice(EN_MONTHS_LONG)} {end}'


def random_sample(rng, sid, split, language, name):
    """Same text layout and truth schema as build_corpus_v2.new_sample, with seeded variety."""
    thai = language == 'th'
    index = rng.randrange(6)  # drives the same optional-field and layout switches as new_sample
    email = None if index % 3 == 0 else sid.replace('_', '.') + '@example.com'
    phone = None if index % 3 == 1 else (f'08{rng.randint(1, 9)}-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}'
                                         if thai else f'+1-555-{rng.randint(1000, 9999)}')
    skills = rng.sample(SKILLS, rng.randint(3, 5))
    company = rng.choice(TH_COMPANIES if thai else EN_COMPANIES) + ' ' + str(rng.randint(1, 9))
    role = 'วิศวกรซอฟต์แวร์' if thai else rng.choice(['Software Engineer', 'Data Analyst', 'Backend Developer'])
    degree, field = ('ปริญญาตรี', 'วิทยาการคอมพิวเตอร์') if thai else ('BSc', 'Computer Science')
    institution = rng.choice(['มหาวิทยาลัยเทคโนโลยีใหม่', 'มหาวิทยาลัยราชภัฏตัวอย่าง']) if thai else rng.choice(
        ['Lakeside University', 'Westbridge Institute of Technology'])
    year = str(rng.randint(2008, 2020) + (543 if thai else 0))
    start, end = _dates(rng, thai)
    achievement = ('พัฒนาระบบด้วย ' if thai else 'Built services using ') + skills[0] + '.'
    jobs = [{'company': company, 'role': role, 'start_date': start, 'end_date': end, 'achievements': [achievement]}]
    schools = [{'institution': institution, 'degree': degree, 'field_of_study': field, 'graduation_year': year}]
    left = [name] + (['Email: ' + email] if email else []) + (['Phone: ' + phone] if phone else [])
    left += ['', 'ทักษะ' if thai else 'Skills', ', '.join(skills)]
    right = ['ประสบการณ์ทำงาน' if thai else 'Employment history']
    sep = ' – ' if index % 2 else ' - '
    right += ([role + ' | ' + company, start + sep + end, '- ' + achievement] if index % 2
              else [company, role, start + sep + end, '- ' + achievement])
    right += ['', 'การศึกษา' if thai else 'Education', institution, degree + ' / ' + field, year]
    columns = [left, right] if index % 2 else [left + [''] + right]
    return {'id': sid, 'split': split, 'language': language, 'layout': 'two-column' if index % 2 else 'single-column',
            'text': '\n'.join(left + [''] + right), 'columns': columns,
            'truth': {'full_name': name, 'contact_email': email, 'contact_phone': phone, 'skills': skills,
                      'experience': jobs, 'education': schools}}


def _build(out_dir, plan, seed, taken):
    """plan: list of (split, id_prefix, count). Names in `taken` (and already used) are rejected."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if 'ResumeThaiV2' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('ResumeThaiV2', str(v2.FONT)))
    v2.DEST = out_dir  # render() writes into the module-level DEST
    rng, used, samples = random.Random(seed), set(taken), []
    for split, prefix, count in plan:
        for i in range(count):
            language = LANGS[i % 3]
            name = _name(rng, language)
            while name in used:
                name = _name(rng, language)
            used.add(name)
            sample = random_sample(rng, f'{prefix}_{language}_{i}', split, language, name)
            v2.render(sample)
            sample['text_sha256'] = sample['sha256']['text']
            samples.append(sample)
    return samples


def _manifest(out_dir, version, purpose, samples, seed):
    manifest = {'version': version, 'annotations_frozen': True, 'seed': seed, 'purpose': purpose,
                'rendering': 'build_corpus_v2.render (Tahoma via Pillow without RAQM).',
                'eval_manifest_sha256': hashlib.sha256(EVAL_MANIFEST.read_bytes()).hexdigest(),
                'samples': samples}
    (Path(out_dir) / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def build_training_set(out_dir, n_train, n_val, seed, taken=()):
    samples = _build(out_dir, [('train', 'train', n_train), ('val', 'val', n_val)], seed, _eval_names() | set(taken))
    return _manifest(out_dir, 'ocr-training-v1', 'QLoRA OCR training; never used for evaluation.', samples, seed)


def build_holdout_v3(out_dir, n, seed, taken=()):
    samples = _build(out_dir, [('holdout', 'hold3', n)], seed, _eval_names() | set(taken))
    return _manifest(out_dir, 'synthetic-resume-v3', 'Fresh untouched OCR holdout for the QLoRA promotion.', samples, seed)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--train', type=int, default=240)
    p.add_argument('--val', type=int, default=30)
    p.add_argument('--holdout', type=int, default=27)
    a = p.parse_args()
    hold_dir = ROOT / 'evaluation/corpus-v3'
    if (hold_dir / 'manifest.json').exists():
        raise SystemExit('corpus-v3 already frozen; refusing overwrite.')
    hold = build_holdout_v3(hold_dir, a.holdout, seed=20261108)
    train = build_training_set(ROOT / 'training/v1', a.train, a.val, seed=7,
                               taken={s['truth']['full_name'] for s in hold['samples']})
    print('holdout', len(hold['samples']), 'train+val', len(train['samples']))
