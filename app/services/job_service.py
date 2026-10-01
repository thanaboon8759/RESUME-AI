import uuid
from typing import List
from app.schemas.job import Job
from app.repositories import job_repository, candidate_repository

def get_jobs(user_id: str) -> List[Job]:
    return job_repository.get_jobs(user_id)

def create_job(job: Job, user_id: str) -> str:
    job_id = job.id or str(uuid.uuid4())
    job.id = job_id
    job_repository.create_job(job, user_id)
    
    if job_id != 'design':
        candidate_repository.clone_candidates_for_job('design', job_id, user_id)
        
    return job_id

def update_job(job_id: str, job: Job, user_id: str):
    job.id = job_id
    job_repository.update_job(job, user_id)
