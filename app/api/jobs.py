from fastapi import APIRouter, Depends
from typing import List
from app.schemas.job import Job
from app.services import job_service
from app.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=List[Job])
async def get_jobs(user = Depends(get_current_user)):
    return job_service.get_jobs(user.id)

@router.post("/", response_model=str)
async def create_job(job: Job, user = Depends(get_current_user)):
    return job_service.create_job(job, user.id)

@router.put("/{job_id}")
async def update_job(job_id: str, job: Job, user = Depends(get_current_user)):
    job_service.update_job(job_id, job, user.id)
    return {"status": "success"}
