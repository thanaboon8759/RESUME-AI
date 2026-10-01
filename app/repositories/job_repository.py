from typing import List
from app.database.supabase.client import supabase
from app.schemas.job import Job

def get_jobs(user_id: str) -> List[Job]:
    if not supabase: return []
    res = supabase.table("jobs").select("*").eq("user_id", user_id).execute()
    jobs = []
    for r in res.data:
        if "created_at" in r:
            r["createdAt"] = r.pop("created_at")
        jobs.append(Job(**r))
    return jobs

def get_job(job_id: str, user_id: str) -> Job | None:
    if not supabase: return None
    res = supabase.table("jobs").select("*").eq("id", job_id).eq("user_id", user_id).execute()
    if not res.data: return None
    r = res.data[0]
    if "created_at" in r:
        r["createdAt"] = r.pop("created_at")
    return Job(**r)

def create_job(job: Job, user_id: str):
    if not supabase: return
    job_data = job.model_dump(mode="json")
    job_data["user_id"] = user_id
    if "createdAt" in job_data:
        job_data["created_at"] = job_data.pop("createdAt")
    supabase.table("jobs").insert(job_data).execute()

def update_job(job: Job, user_id: str):
    if not supabase: return
    job_data = job.model_dump(mode="json")
    job_data["user_id"] = user_id
    if "createdAt" in job_data:
        job_data["created_at"] = job_data.pop("createdAt")
    supabase.table("jobs").upsert(job_data).execute()
