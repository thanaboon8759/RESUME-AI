from pydantic import BaseModel
from typing import List, Optional, Dict
from .core import DecisionEnum, CriterionStatusEnum

class Evidence(BaseModel):
    id: str
    page: int
    quote: str
    bbox: Optional[Dict[str, float]] = None
    charStart: int
    charEnd: int

class Criterion(BaseModel):
    id: str
    label: str
    status: CriterionStatusEnum
    weight: int
    mandatory: bool
    evidence: List[Evidence]

class Candidate(BaseModel):
    id: str
    name: str
    englishName: str
    initials: str
    role: str
    headline: str
    score: int
    experience: str
    location: str
    resumeUrl: str
    extractedText: str
    parseStatus: str
    failureReason: Optional[str] = None
    hasBlocker: bool
    duplicateOf: Optional[str] = None
    criteria: List[Criterion]
    strengths: List[str]
    weaknesses: List[str]
    missingInformation: List[str]
    detectedLanguages: List[str]
    decision: DecisionEnum

class CandidateCreate(BaseModel):
    name: str
    resume_text: str

class DumbdogAIResponse(BaseModel):
    score: int
    decision: DecisionEnum
    reasons: List[str]
