from pydantic import BaseModel
from typing import Optional
from app.schemas.core import DecisionEnum

class DecisionInput(BaseModel):
    candidateId: str
    decision: DecisionEnum
    reasonCode: Optional[str] = None
    note: Optional[str] = None
    secondsSpent: Optional[int] = None

class Decision(DecisionInput):
    id: Optional[str] = None
    jobId: str
    at: str
    actor: str
    reasonLabel: str
    candidateName: str
