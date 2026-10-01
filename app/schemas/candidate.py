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
    resume_url: Optional[str] = None

class DumbdogAIResponse(BaseModel):
    score: int
    decision: DecisionEnum
    reasons: List[str]

class EvidenceResponse(BaseModel):
    quote: str
    block_ids: List[str] = []

class FactEvidence(BaseModel):
    quote: str
    block_ids: List[str] = []

class SkillFact(BaseModel):
    name: str
    evidence: Optional[FactEvidence] = None

class PersonalInfo(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    github: Optional[str] = None
    linkedin: Optional[str] = None

class CandidateProfile(BaseModel):
    personal_info: PersonalInfo
    education: List[dict] = []
    experience: List[dict] = []
    projects: List[dict] = []
    skills: List[SkillFact] = []
    certifications: List[dict] = []
    languages: List[str] = []

class EvidenceRef(BaseModel):
    field: str
    value: str

class CriterionEvaluation(BaseModel):
    label: str
    status: CriterionStatusEnum
    evidence_refs: List[EvidenceRef] = []

class ScreeningResult(BaseModel):
    score: int
    decision: DecisionEnum
    role: Optional[str] = "Unknown"
    headline: Optional[str] = "Evaluated by AI"
    experience_summary: Optional[str] = "Unknown"
    location: Optional[str] = "Unknown"
    strengths: List[str] = []
    weaknesses: List[str] = []
    missingInformation: List[str] = []
    detectedLanguages: List[str] = []
    reasons: List[str] = []
    criteria: List[CriterionEvaluation] = []
    evidence: List[EvidenceResponse] = []
