from typing import List
from app.database.supabase.client import supabase
from app.schemas.job import Job

def get_jobs(user_id: str) -> List[Job]:
    if not supabase: return []
    res = supabase.table("jobs").select("*").eq("user_id", user_id).execute()
    return [Job(**r) for r in res.data]

def create_job(job: Job, user_id: str):
    if not supabase: return
    job_data = job.model_dump(mode="json")
    job_data["user_id"] = user_id
    supabase.table("jobs").insert(job_data).execute()

def update_job(job: Job, user_id: str):
    if not supabase: return
    job_data = job.model_dump(mode="json")
    job_data["user_id"] = user_id
    supabase.table("jobs").upsert(job_data).execute()
