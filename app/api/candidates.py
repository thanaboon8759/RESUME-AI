from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from typing import List
from app.schemas.candidate import Candidate, CandidateCreate
from app.services import candidate_service
from app.auth import get_current_user
from app.database.supabase.client import supabase

router = APIRouter()

@router.get("/jobs/{job_id}/candidates", response_model=List[Candidate])
async def get_job_candidates(job_id: str, user = Depends(get_current_user)):
    return candidate_service.get_candidates(job_id, user.id)

@router.post("/jobs/{job_id}/candidates", response_model=Candidate)
async def create_candidate(job_id: str, candidate_data: CandidateCreate, user = Depends(get_current_user)):
    return await candidate_service.create_candidate(job_id, candidate_data, user.id)

@router.get("/candidates/{candidate_id}", response_model=Candidate)
async def get_candidate(candidate_id: str, user = Depends(get_current_user)):
    cand = candidate_service.get_candidate(candidate_id, user.id)
    if not cand: raise HTTPException(status_code=404, detail="Candidate not found")
    return cand

@router.get("/candidates/{candidate_id}/resume")
async def download_candidate_resume(candidate_id: str, user = Depends(get_current_user)):
    cand = candidate_service.get_candidate(candidate_id, user.id)
    if not cand or not cand.get("resumeUrl"):
        raise HTTPException(status_code=404, detail="Resume not found")
    
    try:
        res = supabase.storage.from_("uploads").download(cand.get("resumeUrl"))
        return Response(content=res, media_type="application/pdf")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Resume not found in storage: {str(e)}")
