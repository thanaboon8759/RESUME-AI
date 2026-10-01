from pydantic import BaseModel
from typing import List

class Reason(BaseModel):
    id: str
    label: str
    appliesTo: List[str]
    hidden: bool
    isDefault: bool

class Member(BaseModel):
    id: str
    email: str
    role: str

class Preferences(BaseModel):
    name: str
    email: str
    company: str
    retention: str
    reasons: List[Reason]
    members: List[Member]
    deleted: List[str]
    jobDeleted: bool
