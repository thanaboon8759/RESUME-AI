from pydantic import BaseModel
from typing import List, Dict, Optional

class Job(BaseModel):
    id: str
    title: str
    jd: str
    required: List[str]
    preferred: List[str]
    weights: Dict[str, int]
    experience: str
    education: str
    location: str
    salary: str
    mandatory: List[str]
    createdAt: Optional[str] = None
