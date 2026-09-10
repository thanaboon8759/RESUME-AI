import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from database import supabase

def seed():
    if not supabase:
        print("Error: Supabase client not initialized. Check your .env file.")
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

    success_count = 0
    error_count = 0

    for candidate in candidates:
        try:
            db_record = {
                "id": candidate["id"],
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
            print(f"✅ Seeded: {candidate['name']} ({candidate['id']})")
        except Exception as e:
            error_count += 1
            print(f"❌ Failed to seed {candidate.get('name', 'Unknown')}: {e}")

    print(f"\nSeeding complete! Success: {success_count}, Errors: {error_count}")

if __name__ == "__main__":
    seed()
