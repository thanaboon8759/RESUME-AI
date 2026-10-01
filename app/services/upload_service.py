from typing import List
from app.schemas.upload import Upload
from app.repositories import upload_repository

def get_uploads(job_id: str, user_id: str) -> List[Upload]:
    return upload_repository.get_uploads(job_id, user_id)

def create_uploads(uploads: List[Upload], user_id: str) -> List[Upload]:
    upload_repository.create_uploads(uploads, user_id)
    return uploads

def update_upload(upload_id: str, upload: Upload, user_id: str):
    upload_repository.update_upload(upload, user_id)
