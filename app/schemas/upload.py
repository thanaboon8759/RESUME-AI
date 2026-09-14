from pydantic import BaseModel
from typing import Optional
from .core import UploadStatusEnum

class Upload(BaseModel):
    id: str
    jobId: str
    name: str
    size: int
    status: UploadStatusEnum
    reason: str
    candidateId: Optional[str] = None
    attempts: int
