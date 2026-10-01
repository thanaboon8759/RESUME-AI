import os

base_path = r"d:\MyProject\backend\app"

def write_file(subpath, content):
    full_path = os.path.join(base_path, subpath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")

write_file("api/preferences.py", """
from fastapi import APIRouter, HTTPException, Depends
from app.schemas.preference import Preferences
from app.services import preference_service
from app.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=Preferences)
async def get_preferences(user = Depends(get_current_user)):
    prefs = preference_service.get_preferences()
    if not prefs: raise HTTPException(status_code=404, detail="Preferences not found")
    return prefs

@router.put("/", response_model=Preferences)
async def update_preferences(prefs: Preferences, user = Depends(get_current_user)):
    return preference_service.update_preferences(prefs)
""")

write_file("api/jobs.py", """
from fastapi import APIRouter, Depends
from typing import List
from app.schemas.job import Job
from app.services import job_service
from app.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=List[Job])
async def get_jobs(user = Depends(get_current_user)):
    return job_service.get_jobs()

@router.post("/", response_model=str)
async def create_job(job: Job, user = Depends(get_current_user)):
    return job_service.create_job(job)

@router.put("/{job_id}")
async def update_job(job_id: str, job: Job, user = Depends(get_current_user)):
    job_service.update_job(job_id, job)
    return {"status": "success"}
""")

write_file("api/candidates.py", """
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.schemas.candidate import Candidate, CandidateCreate
from app.services import candidate_service
from app.auth import get_current_user

router = APIRouter()

@router.get("/{job_id}/candidates", response_model=List[Candidate])
async def get_job_candidates(job_id: str, user = Depends(get_current_user)):
    return candidate_service.get_job_candidates(job_id)

@router.post("/{job_id}/candidates", response_model=Candidate)
async def create_candidate(job_id: str, candidate_data: CandidateCreate, user = Depends(get_current_user)):
    return await candidate_service.create_candidate(job_id, candidate_data)

@router.get("/{candidate_id}", response_model=Candidate)
async def get_candidate(candidate_id: str, user = Depends(get_current_user)):
    cand = candidate_service.get_candidate(candidate_id)
    if not cand: raise HTTPException(status_code=404, detail="Candidate not found")
    return cand
""")

write_file("api/decisions.py", """
from fastapi import APIRouter, Depends
from typing import List
from app.schemas.decision import Decision
from app.services import decision_service
from app.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=List[Decision])
async def get_decisions(user = Depends(get_current_user)):
    return decision_service.get_decisions()

@router.post("/")
async def create_decision(decision: Decision, user = Depends(get_current_user)):
    decision_service.create_decision(decision)
    return {"status": "success"}

@router.delete("/jobs/{job_id}/decisions")
async def clear_decisions(job_id: str, user = Depends(get_current_user)):
    decision_service.clear_decisions(job_id)
    return {"status": "success"}
""")

write_file("api/uploads.py", """
from fastapi import APIRouter, Depends
from typing import List
from app.schemas.upload import Upload
from app.services import upload_service
from app.auth import get_current_user

router = APIRouter()

@router.get("/{job_id}/uploads", response_model=List[Upload])
async def get_uploads(job_id: str, user = Depends(get_current_user)):
    return upload_service.get_uploads(job_id)

@router.post("/", response_model=List[Upload])
async def create_uploads(uploads: List[Upload], user = Depends(get_current_user)):
    return upload_service.create_uploads(uploads)

@router.put("/{upload_id}")
async def update_upload(upload_id: str, upload: Upload, user = Depends(get_current_user)):
    upload_service.update_upload(upload_id, upload)
    return {"status": "success"}
""")

print("Recreated APIs.")
