from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from enum import Enum

class DecisionEnum(str, Enum):
    shortlisted = "shortlisted"
    rejected = "rejected"
    undecided = "undecided"

class CriterionStatusEnum(str, Enum):
    met = "met"
    partial = "partial"
    unmet = "unmet"
    unknown = "unknown"

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
    # Add other basic info needed for the mock AI
    
class DumbdogAIResponse(BaseModel):
    score: int
    decision: DecisionEnum
    reasons: List[str]
    # We map this to the frontend candidate fields in main.py
