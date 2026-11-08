from pydantic import BaseModel, conint
from typing import List, Dict, Optional

class Job(BaseModel):
    id: str
    title: str
    jd: str
    required: List[str]
    preferred: List[str]
    weights: Dict[str, conint(ge=0)]  # negative weights would push scores above 100
    experience: str
    education: str
    location: str
    salary: str
    mandatory: List[str]
    createdAt: Optional[str] = None
