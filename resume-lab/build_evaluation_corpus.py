"""Build versioned synthetic development/holdout fixtures without model outputs."""
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'evaluation' / 'corpus'
FONT = Path('C:/Windows/Fonts/tahoma.ttf')


def build():
    DEST.mkdir(parents=True, exist_ok=True)
    if (DEST / 'manifest.json').exists():
        raise SystemExit('Corpus already frozen. Use a new corpus version instead of overwriting it.')
    old = json.loads((ROOT / 'benchmark-fixtures.json').read_text(encoding='utf-8'))
    samples = []
    for item in old:
        samples.append(dict(id='dev_'+item['id'], split='development', language=item['id'].split('_')[0],
                            text=item['markdown'], truth=item['ground_truth'], layout='single-column'))
    # Independent identities/templates reserved for final evaluation, never prompt tuning.
    records = [
        ('hold_en_missing','en','single-column','Morgan Reed',None,None,['Rust','Linux','Git'],
         'Tooling Developer','North Workshop','2021','2023','Built command-line tools using Rust and Git.',
         'Example Institute','Diploma','Software Development','2020'),
        ('hold_th_missing','th','single-column','กมล ชัยดี',None,None,['Python','SQL','Docker'],
         'นักพัฒนาระบบ','บริษัท ระบบตัวอย่าง จำกัด','2563','2566','พัฒนาระบบรายงานด้วย Python และ SQL',
         'มหาวิทยาลัยตัวอย่าง','ปริญญาตรี','วิทยาการคอมพิวเตอร์','2562'),
        ('hold_bi_columns','bi','two-column','ปวีณา สายใจ (Paweena Saijai)','paweena@example.com','080-555-0101',['Java','Spring','PostgreSQL'],
         'Backend Engineer','Example Services','Mar 2022','Present','Built APIs using Java and Spring.',
         'Example University','BSc','Computer Science','2021'),
        ('hold_en_columns','en','two-column','Alex Rowan','alex.rowan@example.com','+1-555-0142',['TypeScript','React','CSS'],
         'Frontend Developer','Example Design','June 2020','May 2024','Built accessible interfaces with React and CSS.',
         'Example College','BSc','Computing','2019'),
        ('hold_th_columns','th','two-column','อรทัย พูนสุข','orathai@example.com','089-555-0123',['Excel','Power BI','SQL'],
         'นักวิเคราะห์ข้อมูล','บริษัท ข้อมูลสาธิต จำกัด','มกราคม 2562','ธันวาคม 2565','สร้างรายงานด้วย Power BI และ SQL',
         'มหาวิทยาลัยสาธิต','ปริญญาโท','สถิติ','2561'),
        ('hold_bi_missing','bi','single-column','Narin Demo (นรินทร์ สาธิต)',None,'081-555-0199',['Go','Kubernetes','Linux'],
         'Platform Engineer','บริษัท Example Cloud','2020','2024','ดูแลบริการบน Kubernetes และ Linux',
         'Demo University','BEng','Computer Engineering','2019'),
    ]
    for row in records:
        ident, lang, layout, name, email, phone, skills, role, company, start, end, achievement, institution, degree, field, year = row
        thai = lang == 'th'
        left = [name]
        if email: left.append('Email: '+email)
        if phone: left.append('Phone: '+phone)
        left += ['', 'ทักษะ' if thai else 'Skills', ', '.join(skills)]
        right = ['ประสบการณ์ทำงาน' if thai else 'Experience', role, company, start+' - '+end, achievement,
                 '', 'การศึกษา' if thai else 'Education', institution, degree, field, year]
        truth = {'full_name':name,'contact_email':email,'contact_phone':phone,'skills':skills,
                 'experience':[{'company':company,'role':role,'start_date':start,'end_date':end,'achievements':[achievement]}],
                 'education':[{'institution':institution,'degree':degree,'field_of_study':field,'graduation_year':year}]}
        samples.append(dict(id=ident,split='holdout',language=lang,layout=layout,text='\n'.join(left+['']+right),
                            truth=truth, columns=[left,right]))
    font = ImageFont.truetype(str(FONT), 26)
    pdfmetrics.registerFont(TTFont('ResumeThai', str(FONT)))
    for sample in samples:
        stem = sample['id']
        text = sample['text'].replace('\r\n','\n').strip()
        (DEST / (stem+'.txt')).write_text(text,encoding='utf-8')
        image = Image.new('RGB',(1700,2200),'white')
        draw = ImageDraw.Draw(image)
        columns = sample.get('columns') if sample['layout']=='two-column' else [text.splitlines()]
        for col, lines in enumerate(columns):
            x, y = (70 if col==0 else 900), 65
            max_width = 720 if len(columns)>1 else 1560
            for line in lines:
                # Wrap by glyph width rather than dropping overflowing source text.
                rendered = ''
                for character in line:
                    if rendered and draw.textlength(rendered+character,font=font)>max_width:
                        draw.text((x,y),rendered,font=font,fill='black'); y+=40; rendered=''
                    rendered+=character
                draw.text((x,y),rendered,font=font,fill='black'); y+=40
            if y > 2150: raise ValueError(f'{stem} exceeded page bounds')
        image.save(DEST/(stem+'.png'))
        image.save(DEST/(stem+'-scan.pdf'),'PDF',resolution=144)
        pdf = canvas.Canvas(str(DEST/(stem+'-digital.pdf')),pagesize=(850,1100))
        pdf.setFont('ResumeThai',13)
        for col, lines in enumerate(columns):
            x,y = (35 if col==0 else 450),1060
            for line in lines:
                # Digital variant preserves text; intentionally shares test content.
                while len(line)>100:
                    pdf.drawString(x,y,line[:100]);y-=20;line=line[100:]
                pdf.drawString(x,y,line);y-=20
        pdf.save()
        sample['files']={kind:stem+suffix for kind,suffix in [('text','.txt'),('image','.png'),('scanned_pdf','-scan.pdf'),('digital_pdf','-digital.pdf')]}
        sample['sha256']={kind:hashlib.sha256((DEST/name).read_bytes()).hexdigest() for kind,name in sample['files'].items()}
        sample.pop('columns',None)
    manifest={'version':'synthetic-resume-v1','purpose':'Development fixes and a separately frozen final evaluation; not population-level validation.',
              'rendering':'Tahoma raster text via Pillow without RAQM; complex Thai shaping may differ from native documents. Inspect images and report this limitation.',
              'font_sha256':hashlib.sha256(FONT.read_bytes()).hexdigest(),'samples':samples}
    (DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Frozen {len(samples)} identities, {len(samples)*4} document variants in {DEST}')


if __name__=='__main__':
    build()
