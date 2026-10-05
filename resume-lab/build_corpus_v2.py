"""Expand development coverage and freeze fresh identities before inference."""
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT=Path(__file__).resolve().parent
DEST=ROOT/'evaluation/corpus-v2'
FONT=Path('C:/Windows/Fonts/tahoma.ttf')


def render(sample):
    stem=sample['id']
    text=sample['text'].strip()
    (DEST/(stem+'.txt')).write_text(text,encoding='utf-8')
    columns=sample.pop('columns')
    image=Image.new('RGB',(1700,2200),'white')
    draw=ImageDraw.Draw(image)
    font=ImageFont.truetype(str(FONT),26)
    pdf=canvas.Canvas(str(DEST/(stem+'-digital.pdf')),pagesize=(850,1100))
    pdf.setFont('ResumeThaiV2',13)
    for index,lines in enumerate(columns):
        x,y=(70 if index==0 else 900),65
        width=720 if len(columns)>1 else 1560
        for line in lines:
            wrapped=['']
            for char in line:
                if wrapped[-1] and draw.textlength(wrapped[-1]+char,font=font)>width:
                    wrapped.append('')
                wrapped[-1]+=char
            for linepart in wrapped:
                draw.text((x,y),linepart,font=font,fill='black')
                pdf.drawString(x/2,1100-y/2,linepart)
                y+=40
        if y>2150:
            raise ValueError('Page overflow: '+stem)
    pdf.save()
    image.save(DEST/(stem+'.png'))
    image.save(DEST/(stem+'-scan.pdf'),'PDF',resolution=144)
    sample['files']={k:stem+s for k,s in [('text','.txt'),('image','.png'),('scanned_pdf','-scan.pdf'),('digital_pdf','-digital.pdf')]}
    sample['sha256']={k:hashlib.sha256((DEST/f).read_bytes()).hexdigest() for k,f in sample['files'].items()}


def new_sample(split,index,language,name):
    dev=split=='development'
    tag=('practice' if dev else 'reserved')+'_'+str(index)
    thai=language=='th'
    # Different date styles, missing fields, multi-job histories and layouts in both splits.
    dates=([('2017','2020'),('Feb 2021','Current'),('ม.ค. 2560','ธ.ค. 2563'),('2564','ปัจจุบัน'),('04/2019','11/2022'),('September 2022','Present')] if dev else
           [('2015','2019'),('Jul 2020','Dec 2023'),('ก.พ. 2559','พ.ย. 2562'),('2563','2567'),('02/2018','08/2021'),('October 2021','Present'),('2016','2024'),('เมษายน 2561','ปัจจุบัน'),('Jun 2017','Jan 2022')])[index]
    email=None if index%3==0 else tag+'@example.com'
    phone=None if index%3==1 else ('080-700-'+str(2000+index) if thai else '+1-555-'+str(2000+index))
    skills=([['Python','SQLite','Git'],['Java','JUnit','Maven'],['SQL','Excel','Power BI'],['Docker','Linux','Bash'],['TypeScript','Vue','CSS'],['Go','PostgreSQL','Redis']] if dev else
            [['Rust','Linux','Git'],['C#','SQL Server','Azure'],['Python','Pandas','SQL'],['JavaScript','HTML','CSS'],['Java','Spring','Docker'],['Kotlin','Gradle','Git'],['Excel','SQL','Tableau'],['Python','FastAPI','PostgreSQL'],['Go','Linux','Kubernetes']])[index]
    company=('บริษัท ฝึกงานข้อมูล' if dev and thai else 'บริษัท ทดสอบระบบ' if thai else 'Practice Software' if dev else 'Reserved Solutions')+' '+str(index+1)
    role='วิศวกรซอฟต์แวร์' if thai else 'Software Engineer'
    degree='ปริญญาตรี' if thai else 'BSc'
    field='วิทยาการคอมพิวเตอร์' if thai else 'Computer Science'
    institution=('มหาวิทยาลัยฝึกฝน' if dev else 'มหาวิทยาลัยตัวอย่างใหม่') if thai else ('Practice College' if dev else 'Reserved Technical College')
    year='2558' if thai else '2014'
    achievement=('พัฒนาระบบด้วย ' if thai else 'Built services using ')+skills[0]+'.'
    job={'company':company,'role':role,'start_date':dates[0],'end_date':dates[1],'achievements':[achievement]}
    education={'institution':institution,'degree':degree,'field_of_study':field,'graduation_year':year}
    jobs=[job]; schools=[education]
    left=[name]
    if email:left+=['Email: '+email]
    if phone:left+=['Phone: '+phone]
    left+=['','ทักษะ' if thai else 'Skills',', '.join(skills)]
    right=['ประสบการณ์ทำงาน' if thai else 'Employment history']
    separator=' – ' if index%2 else ' - '
    if index%2:
        right += [role+' | '+company, dates[0]+separator+dates[1],'- '+achievement]
    else:
        right += [company, role, dates[0]+separator+dates[1],'- '+achievement]
    if index%3==2:
        earlier={'company':('บริษัท เริ่มต้น' if thai else 'Earlier Studio')+' '+str(index),
                 'role':'ผู้ช่วยนักพัฒนา' if thai else 'Junior Developer',
                 'start_date':'2556' if thai else '2012','end_date':'2558' if thai else '2014',
                 'achievements':['ดูแลระบบภายใน' if thai else 'Maintained internal software.']}
        jobs.append(earlier)
        right+=['',earlier['role'],earlier['company'],earlier['start_date']+' - '+earlier['end_date'],'- '+earlier['achievements'][0]]
    right+=['','การศึกษา' if thai else 'Education',institution, degree+' / '+field,year]
    if index%3==1:
        extra={'institution':'Learning Academy '+str(index),'degree':'Diploma','field_of_study':'Information Technology','graduation_year':'2010'}
        schools.append(extra)
        right+=['',extra['institution'],extra['degree']+' in '+extra['field_of_study'],extra['graduation_year']]
    columns=[left,right] if index%2 else [left+['']+right]
    return {'id':('dev2_' if dev else 'hold2_')+language+'_'+str(index),'split':split,'language':language,
            'layout':'two-column' if index%2 else 'single-column','text':'\n'.join(left+['']+right),'columns':columns,
            'truth':{'full_name':name,'contact_email':email,'contact_phone':phone,'skills':skills,'experience':jobs,'education':schools}}


def build():
    if (DEST/'manifest.json').exists():raise SystemExit('Already frozen; refusing overwrite.')
    DEST.mkdir(parents=True,exist_ok=True)
    original=ROOT/'evaluation/corpus/manifest.json'
    corrections=json.loads((ROOT/'evaluation/development-labels-v2.json').read_text(encoding='utf-8'))
    if corrections['source_manifest_sha256']!=hashlib.sha256(original.read_bytes()).hexdigest():raise ValueError('Wrong source corpus')
    samples=[]
    for sample in json.loads(original.read_text(encoding='utf-8'))['samples']:
        if sample['split']!='development':continue
        sample['truth'].update(corrections['changes'].get(sample['id'],{}))
        for filename in sample['files'].values():shutil.copyfile(original.parent/filename,DEST/filename)
        samples.append(sample)
    pdfmetrics.registerFont(TTFont('ResumeThaiV2',str(FONT)))
    groups=[('development',[('en','Taylor Practice'),('en','Dr. Casey Lane (C. Lane)'),('th','ชลิต ฝึกฝน'),('th','ดร. มาลี ทดลอง'),('bi','พิชญ์ ทดสอบ (Pitch Test)'),('bi','Robin Practice (รวิ ฝึกฝน)')]),
            ('holdout',[('en','Jordan Hart'),('en','Dr. Drew Wells'),('th','กิตติ วัฒนชัย'),('th','นางสาว วารี ใจกล้า'),('bi','ณัฐธิดา ตั้งใจ (Nattida Tangjai)'),('bi','Evan Finch (อีวาน ฟินช์)'),('en','Sam Arden (S. Arden)'),('th','ดร. สุภา แสงทอง'),('bi','อรุณ พัฒนกิจ (Arun Pattanakit)')])]
    for split,names in groups:
        for index,(language,name) in enumerate(names):
            sample=new_sample(split,index,language,name)
            render(sample);samples.append(sample)
    manifest={'version':'synthetic-resume-v2','annotations_frozen':True,
              'source_corpus_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
              'annotation_overlay_sha256':hashlib.sha256((ROOT/'evaluation/development-labels-v2.json').read_bytes()).hexdigest(),
              'purpose':'Expanded development plus fresh untouched holdout; old failed holdout excluded. Synthetic template families overlap, so no population accuracy claim.',
              'rendering':'Tahoma via Pillow without RAQM. Same glyph-width wrapping in images and digital PDFs.',
              'font_sha256':hashlib.sha256(FONT.read_bytes()).hexdigest(),'samples':samples}
    (DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (DEST/'builder-snapshot.py').write_bytes(Path(__file__).read_bytes())
    print('Frozen',len(samples),'identities; development',sum(s['split']=='development' for s in samples),'holdout',sum(s['split']=='holdout' for s in samples))


if __name__=='__main__':build()
