from typing import List
from app.schemas.decision import Decision
from fastapi import HTTPException
from app.repositories import candidate_repository, decision_repository

def get_decisions(user_id: str) -> List[Decision]:
    return decision_repository.get_decisions(user_id)

def create_decision(decision: Decision, user_id: str):
    job_id = candidate_repository.get_candidate_job_id(decision.candidateId, user_id)
    if not job_id:
        raise HTTPException(status_code=404, detail="Candidate not found")
    # The candidate's stored job wins over the jobId the client sent.
    decision_repository.create_decision(decision.model_copy(update={"jobId": job_id}), user_id)

def clear_decisions(job_id: str, user_id: str):
    decision_repository.clear_decisions(job_id, user_id)
