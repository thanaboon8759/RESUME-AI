import re
from typing import List
from fastapi import HTTPException
from app.schemas.upload import Upload
from app.repositories import job_repository, upload_repository


def _safe_segment(value: str) -> bool:
    """Storage path pieces: no separators or dot-only names, so uploads stay in their job folder."""
    # Denylist, not \w: Thai vowel and tone marks (e.g. ่ ู) are not \w, and Thai filenames are normal here.
    return bool(value) and value not in (".", "..") and re.search(r"[/\\\x00-\x1f\x7f]", value) is None


def _check_rows(uploads: List[Upload], user_id: str):
    """Rows name a storage path ({jobId}/{id}_{name}), so the job must be the caller's and the pieces safe."""
    for u in uploads:
        if not job_repository.get_job(u.jobId, user_id):
            raise HTTPException(status_code=404, detail="Job not found")
        if not _safe_segment(u.id) or not _safe_segment(u.name):
            raise HTTPException(status_code=400, detail="Invalid upload id or filename")

def get_uploads(job_id: str, user_id: str) -> List[Upload]:
    return upload_repository.get_uploads(job_id, user_id)

def create_uploads(uploads: List[Upload], user_id: str) -> List[Upload]:
    _check_rows(uploads, user_id)
    upload_repository.create_uploads(uploads, user_id)
    return uploads

def update_upload(upload_id: str, upload: Upload, user_id: str):
    existing = upload_repository.get_upload(upload_id)
    if existing and existing["user_id"] != user_id:  # the upsert would otherwise take the row over
        raise HTTPException(status_code=404, detail="Upload not found")
    upload = upload.model_copy(update={"id": upload_id})
    _check_rows([upload], user_id)
    upload_repository.update_upload(upload, user_id)
