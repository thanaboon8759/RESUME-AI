from typing import List
from app.database.supabase.client import supabase
from app.schemas.upload import Upload

def get_uploads(job_id: str, user_id: str) -> List[Upload]:
    if not supabase: return []
    res = supabase.table("uploads").select("*").eq("job_id", job_id).eq("user_id", user_id).execute()
    return [Upload(
        id=r["id"], jobId=r["job_id"], name=r["name"], size=r["size"],
        status=r["status"], reason=r["reason"], candidateId=r["candidate_id"], attempts=r["attempts"]
    ) for r in res.data]

def create_uploads(uploads: List[Upload], user_id: str):
    if not supabase: return
    records = []
    for u in uploads:
        records.append({
            "id": u.id, "job_id": u.jobId, "user_id": user_id, "name": u.name, "size": u.size,
            "status": u.status.value, "reason": u.reason, "candidate_id": u.candidateId, "attempts": u.attempts
        })
    supabase.table("uploads").insert(records).execute()

def update_upload(upload: Upload, user_id: str):
    if not supabase: return
    db_record = {
        "id": upload.id, "job_id": upload.jobId, "user_id": user_id, "name": upload.name, "size": upload.size,
        "status": upload.status.value, "reason": upload.reason, "candidate_id": upload.candidateId, "attempts": upload.attempts
    }
    supabase.table("uploads").upsert(db_record).execute()
