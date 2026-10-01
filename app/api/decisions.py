from fastapi import APIRouter, Depends
from typing import List
from app.schemas.decision import Decision
from app.services import decision_service
from app.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=List[Decision])
async def get_decisions(user = Depends(get_current_user)):
    return decision_service.get_decisions(user.id)

@router.post("/")
async def create_decision(decision: Decision, user = Depends(get_current_user)):
    decision_service.create_decision(decision, user.id)
    return {"status": "success"}

@router.delete("/jobs/{job_id}/decisions")
async def clear_decisions(job_id: str, user = Depends(get_current_user)):
    decision_service.clear_decisions(job_id, user.id)
    return {"status": "success"}
