from typing import List
from app.database.supabase.client import supabase
from app.schemas.candidate import Candidate

def get_candidates_for_job(job_id: str, user_id: str) -> List[Candidate]:
    if not supabase: return []
    res = supabase.table("candidates").select("full_data").eq("job_id", job_id).eq("user_id", user_id).execute()
    return [r["full_data"] for r in res.data]

def get_candidate(candidate_id: str, user_id: str) -> Candidate | None:
    if not supabase: return None
    res = supabase.table("candidates").select("full_data").eq("id", candidate_id).eq("user_id", user_id).execute()
    return res.data[0]["full_data"] if res.data else None

def clone_candidates_for_job(source_job_id: str, new_job_id: str, user_id: str):
    if not supabase: return
    cands_resp = supabase.table("candidates").select("*").eq("job_id", source_job_id).eq("user_id", user_id).limit(15).execute()
    for row in cands_resp.data:
        new_cand_id = f"{new_job_id}-{row['id']}"
        row['id'] = new_cand_id
        row['job_id'] = new_job_id
        row['decision'] = 'undecided'
        
        full_data = row['full_data']
        full_data['id'] = new_cand_id
        full_data['decision'] = 'undecided'
        row['full_data'] = full_data
        
        if 'created_at' in row: del row['created_at']
        supabase.table("candidates").insert(row).execute()

def create_candidate(candidate_id: str, job_id: str, name: str, ai_evaluation, rich_candidate: Candidate, user_id: str):
    if not supabase: return
    db_record = {
        "id": candidate_id, "user_id": user_id, "job_id": job_id, "candidate_name": name,
        "position": "Backend Developer", "score": ai_evaluation.score, "decision": ai_evaluation.decision.value,
        "reason": ai_evaluation.reasons, "full_data": rich_candidate.model_dump(mode="json")
    }
    supabase.table("candidates").insert(db_record).execute()
