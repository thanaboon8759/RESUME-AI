import json
import os
import uuid
from pathlib import Path
from datetime import datetime

def escape_sql(val):
    if val is None:
        return 'NULL'
    if isinstance(val, bool):
        return 'TRUE' if val else 'FALSE'
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, (dict, list)):
        s = json.dumps(val, ensure_ascii=False)
        return "'" + s.replace("'", "''") + "'"
    return "'" + str(val).replace("'", "''") + "'"

def main():
    fixtures_path = Path(__file__).parent.parent / "frontend" / "src" / "mocks" / "fixtures.json"
    supabase_dir = Path(__file__).parent.parent / "supabase" / "migrations"
    supabase_dir.mkdir(parents=True, exist_ok=True)
    seed_sql_path = supabase_dir / "seed.sql"
    
    with open(fixtures_path, 'r', encoding='utf-8') as f:
        candidates = json.load(f)
        
    sql = []
    
    # 1. Preferences
    preferences_id = 'default'
    reasons = [
        {"id": "reason-0-0", "label": "ผลงานตรงกับที่ต้องการ", "appliesTo": ["shortlisted"], "hidden": False, "isDefault": True},
        {"id": "reason-0-1", "label": "ประสบการณ์เทียบเคียงได้แม้ชื่อตำแหน่งไม่ตรง", "appliesTo": ["shortlisted"], "hidden": False, "isDefault": True},
        {"id": "reason-0-2", "label": "น่าสนใจแม้ระบบให้คะแนนต่ำ", "appliesTo": ["shortlisted"], "hidden": False, "isDefault": True},
        {"id": "reason-1-0", "label": "ประสบการณ์ไม่ตรงสายงาน", "appliesTo": ["rejected"], "hidden": False, "isDefault": True},
        {"id": "reason-1-1", "label": "ขาดทักษะหลัก", "appliesTo": ["rejected"], "hidden": False, "isDefault": True},
        {"id": "reason-1-2", "label": "เกินระดับตำแหน่ง", "appliesTo": ["rejected"], "hidden": False, "isDefault": True},
        {"id": "reason-1-3", "label": "สถานที่ทำงานไม่ตรง", "appliesTo": ["rejected"], "hidden": False, "isDefault": True},
        {"id": "reason-1-4", "label": "ช่วงเงินเดือนไม่ตรง", "appliesTo": ["rejected"], "hidden": False, "isDefault": True},
        {"id": "reason-1-5", "label": "ข้อมูลในเรซูเม่ไม่พอตัดสิน", "appliesTo": ["rejected"], "hidden": False, "isDefault": True},
        {"id": "reason-2-0", "label": "ต้องการข้อมูลเพิ่มเติม", "appliesTo": ["undecided"], "hidden": False, "isDefault": True},
        {"id": "reason-2-1", "label": "รอหารือกับทีม", "appliesTo": ["undecided"], "hidden": False, "isDefault": True},
    ]
    members = [{"id": "owner", "email": "hr@example.com", "role": "admin"}]
    
    sql.append(f"""
INSERT INTO public.preferences (id, name, email, company, retention, reasons, members, deleted, job_deleted)
VALUES (
    'default', 
    'ทีมทรัพยากรบุคคล', 
    'hr@example.com', 
    'Hireproof Studio', 
    '90', 
    {escape_sql(reasons)}, 
    {escape_sql(members)}, 
    '[]', 
    FALSE
) ON CONFLICT (id) DO NOTHING;
""")

    # 2. Jobs
    job_id = "design"
    weights = {"Figma": 5, "User Research": 4, "English": 3}
    required = ["Figma", "User Research"]
    preferred = ["English"]
    mandatory = ["ทำงานที่กรุงเทพฯ ได้"]
    
    sql.append(f"""
INSERT INTO public.jobs (id, title, jd, required, preferred, weights, experience, education, location, salary, mandatory)
VALUES (
    '{job_id}', 
    'Senior Product Designer', 
    '', 
    {escape_sql(required)}, 
    {escape_sql(preferred)}, 
    {escape_sql(weights)}, 
    '3', 
    'ปริญญาตรี', 
    'กรุงเทพมหานคร', 
    '50,000–80,000', 
    {escape_sql(mandatory)}
) ON CONFLICT (id) DO NOTHING;
""")

    # 3. Candidates
    for c in candidates:
        c_id = c['id']
        reason_list = c.get('strengths', []) + c.get('weaknesses', [])
        
        sql.append(f"""
INSERT INTO public.candidates (id, job_id, candidate_name, position, score, decision, reason, full_data)
VALUES (
    {escape_sql(c_id)},
    '{job_id}',
    {escape_sql(c.get('name'))},
    {escape_sql(c.get('role', 'Unknown'))},
    {c.get('score', 0)},
    {escape_sql(c.get('decision', 'undecided'))},
    {escape_sql(reason_list)},
    {escape_sql(c)}
) ON CONFLICT (id) DO UPDATE SET 
    full_data = EXCLUDED.full_data,
    score = EXCLUDED.score,
    decision = EXCLUDED.decision;
""")

    with open(seed_sql_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(sql))
    
    print(f"Generated seed.sql at {seed_sql_path}")

if __name__ == '__main__':
    main()
