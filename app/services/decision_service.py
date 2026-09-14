from typing import List
from app.schemas.decision import Decision
from app.repositories import decision_repository

def get_decisions(user_id: str) -> List[Decision]:
    return decision_repository.get_decisions(user_id)

def create_decision(decision: Decision, user_id: str):
    decision_repository.create_decision(decision, user_id)

def clear_decisions(job_id: str, user_id: str):
    decision_repository.clear_decisions(job_id, user_id)
