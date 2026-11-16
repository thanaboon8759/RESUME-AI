import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.database.supabase.client import supabase

def seed():
    if not supabase:
        print("Error: Supabase client not initialized. Check your .env file.")
        sys.exit(1)

    # Credentials come from .env only: this repo is public.
    email, password = os.getenv("SEED_EMAIL"), os.getenv("SEED_PASSWORD")
    if not email or not password:
        print("Error: set SEED_EMAIL and SEED_PASSWORD in .env to the user the seed data belongs to.")
        sys.exit(1)

    print(f"Logging in as {email}...")
    try:
        auth_response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user_id = auth_response.user.id
        print(f"Logged in, user_id: {user_id}")
    except Exception as e:
        print(f"Error: login failed: {e}")
        sys.exit(1)

    # Path to fixtures.json
    fixtures_path = Path(__file__).parent.parent / "frontend" / "src" / "mocks" / "fixtures.json"
    
    if not fixtures_path.exists():
        print(f"Error: Could not find fixtures file at {fixtures_path}")
        sys.exit(1)

    print(f"Loading fixtures from {fixtures_path}")
    with open(fixtures_path, 'r', encoding='utf-8') as f:
        candidates = json.load(f)

    print(f"Found {len(candidates)} candidates to seed.")

    # 1. Seed Preferences
    reasons = []
    labels = [
        ["ผลงานตรงกับที่ต้องการ", "ประสบการณ์เทียบเคียงได้แม้ชื่อตำแหน่งไม่ตรง", "น่าสนใจแม้ระบบให้คะแนนต่ำ"],
        ["ประสบการณ์ไม่ตรงสายงาน", "ขาดทักษะหลัก", "เกินระดับตำแหน่ง", "สถานที่ทำงานไม่ตรง", "ช่วงเงินเดือนไม่ตรง", "ข้อมูลในเรซูเม่ไม่พอตัดสิน"],
        ["ต้องการข้อมูลเพิ่มเติม", "รอหารือกับทีม"]
    ]
    applies_to_map = ["shortlisted", "rejected", "undecided"]
    for g, group in enumerate(labels):
        for i, label in enumerate(group):
            reasons.append({
                "id": f"reason-{g}-{i}",
                "label": label,
                "appliesTo": [applies_to_map[g]],
                "hidden": False,
                "isDefault": True
            })

    prefs = {
        "id": user_id,  # one preferences row per user (see preference_repository)
        "user_id": user_id,
        "name": "ทีมทรัพยากรบุคคล",
        "email": "hr@example.com",
        "company": "Hireproof Studio",
        "retention": "90",
        "reasons": reasons,
        "members": [{"id": "owner", "email": "hr@example.com", "role": "admin"}],
        "deleted": [],
        "job_deleted": False
    }
    supabase.table("preferences").upsert(prefs).execute()
    print("[OK] Seeded: Preferences")

    # 2. Seed Jobs
    from datetime import datetime, timezone
    job = {
        "id": "design",
        "user_id": user_id,
        "title": "Senior Product Designer",
        "jd": "",
        "required": ["Figma", "User Research"],
        "preferred": ["English"],
        "weights": {"Figma": 5, "User Research": 4, "English": 3},
        "experience": "3",
        "education": "ปริญญาตรี",
        "location": "กรุงเทพมหานคร",
        "salary": "50,000–80,000",
        "mandatory": ["ทำงานที่กรุงเทพฯ ได้"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    supabase.table("jobs").upsert(job).execute()
    print("[OK] Seeded: Job (design)")

    # 3. Seed Candidates
    success_count = 0
    error_count = 0

    for candidate in candidates:
        try:
            db_record = {
                "id": candidate["id"],
                "user_id": user_id,
                "job_id": "design",
                "candidate_name": candidate["name"],
                "position": candidate.get("role", "Unknown"),
                "score": candidate.get("score", 0),
                "decision": candidate.get("decision", "undecided"),
                "reason": candidate.get("strengths", []) + candidate.get("weaknesses", []), # Mocking reason array
                "full_data": candidate # Store the entire object for the UI
            }
            
            # Using upsert to avoid duplicates if run multiple times
            result = supabase.table("candidates").upsert(db_record).execute()
            success_count += 1
            print(f"[OK] Seeded: {candidate['name']} ({candidate['id']})")
        except Exception as e:
            error_count += 1
            print(f"[ERROR] Failed to seed {candidate.get('name', 'Unknown')}: {e}")

    print(f"\nSeeding complete! Success: {success_count}, Errors: {error_count}")

if __name__ == "__main__":
    seed()
