from typing import List
from fastapi import HTTPException
from app.schemas.upload import Upload
from app.repositories import upload_repository

def get_uploads(job_id: str, user_id: str) -> List[Upload]:
    return upload_repository.get_uploads(job_id, user_id)

def create_uploads(uploads: List[Upload], user_id: str) -> List[Upload]:
    upload_repository.create_uploads(uploads, user_id)
    return uploads

def update_upload(upload_id: str, upload: Upload, user_id: str):
    existing = upload_repository.get_upload(upload_id)
    if existing and existing["user_id"] != user_id:  # the upsert would otherwise take the row over
        raise HTTPException(status_code=404, detail="Upload not found")
    upload_repository.update_upload(upload.model_copy(update={"id": upload_id}), user_id)
