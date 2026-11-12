from pydantic import BaseModel, conint
from typing import List, Dict, Optional

class Job(BaseModel):
    id: str
    title: str
    jd: str
    required: List[str]
    preferred: List[str]
    weights: Dict[str, int]  # stays loose so old DB rows still load; JobInput checks new input
    experience: str
    education: str
    location: str
    salary: str
    mandatory: List[str]
    createdAt: Optional[str] = None


class JobInput(Job):
    """Job as sent by HR: negative weights would push scores above 100."""
    weights: Dict[str, conint(ge=0)]
