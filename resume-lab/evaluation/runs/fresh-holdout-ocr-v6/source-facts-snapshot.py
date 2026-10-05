"""Conservative source-backed repairs for observed extraction omissions."""
import re

MONTHS=r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.|มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม)'
DATE=re.compile(r'(?:\d{4}|\d{1,2}[/-]\d{4}|\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?|'+MONTHS+r'\s+\d{4})',re.I)


def clean_line(line):
    return line.strip().strip('#* \t')


def refine(profile, text):
    """Only use unique exact source spans. Return an auditable list of changes."""
    lines=[clean_line(line) for line in text.splitlines()]
    changes=[]

    def set_value(obj, field, value, path, evidence):
        old=getattr(obj,field)
        if old!=value:
            setattr(obj,field,value)
            changes.append({'field':path+'.'+field,'before':old,'after':value,'source':evidence})

    name=profile.full_name.strip()
    if name:
        aliases=[line for line in lines[:10] if line.startswith(name) and re.fullmatch(r'(\s*\([^()\n]+\))+',line[len(name):])]
        if len(set(aliases))==1:
            set_value(profile,'full_name',aliases[0],'profile',aliases[0])

    for index,job in enumerate(profile.experience):
        path=f'experience[{index}]'
        # E.g. a printed organization suffix omitted by the model; do not fuzzy-match names.
        spans=[part.strip() for line in lines for part in re.split(r'\s+[|\u2013\u2014-]\s+',line)]
        expanded=[part.strip() for i,line in enumerate(lines)
                  if any(job.role and job.role in nearby for nearby in lines[max(0,i-1):i+2])
                  for part in re.split(r'\s+[|\u2013\u2014-]\s+',line)
                  if job.company and re.fullmatch(re.escape(job.company)+r'\s+\d+',part.strip())]
        if job.company not in spans and len(set(expanded))==1:
            set_value(job,'company',expanded[0],path,expanded[0])
        anchors=[i for i,line in enumerate(lines) if job.company and job.company in [p.strip() for p in re.split(r'\s+[|\u2013\u2014-]\s+',line)] and
                 any(job.role and job.role in nearby for nearby in lines[max(0,i-1):i+2])]
        if len(anchors)!=1:
            continue
        for line in lines[anchors[0]+1:anchors[0]+4]:
            if line.casefold() in {'education','การศึกษา','ประวัติการศึกษา'} or any(
                    other is not job and any(value and value in line for value in [other.company,other.role])
                    for other in profile.experience):
                break
            parts=re.split(r'\s+[–—-]\s+|\s+(?:to|ถึง)\s+',line)
            if len(parts)!=2 or not DATE.fullmatch(parts[0]):
                continue
            if not (DATE.fullmatch(parts[1]) or parts[1].casefold() in {'present','current','ปัจจุบัน'}):
                continue
            # Restrict spans to date-sized strings and exclude sentences/section labels.
            if any(len(part)>32 or ':' in part for part in parts):
                continue
            set_value(job,'start_date',parts[0],path,line)
            set_value(job,'end_date',parts[1],path,line)
            break

    degree_start=re.compile(r'^(?:Bachelor|Master|Doctor|Diploma|Certificate|B\.?Sc\.?|M\.?Sc\.?|B\.?S\.?|M\.?S\.?|BEng|MEng)\b',re.I)
    for index,education in enumerate(profile.education):
        anchors=[i for i,line in enumerate(lines) if education.institution and education.institution in line]
        if len(anchors)!=1:
            continue
        block=lines[max(0,anchors[0]-1):anchors[0]+3]
        for combined in [education.degree,education.field_of_study]:
            if not combined or not any(combined in line for line in block) or not degree_start.search(combined):
                continue
            parts=re.split(r'\s+in\s+|\s+/\s+',combined,maxsplit=1,flags=re.I)
            if len(parts)==2 and all(parts):
                if education.degree not in {None,'',combined,parts[0]} or education.field_of_study not in {None,'',combined,parts[1]}:
                    continue
                set_value(education,'degree',parts[0],f'education[{index}]',combined)
                set_value(education,'field_of_study',parts[1],f'education[{index}]',combined)
                break
    return changes
