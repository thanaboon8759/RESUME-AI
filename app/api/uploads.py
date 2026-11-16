import asyncio
from fastapi import APIRouter, Depends, UploadFile, File, Form, Response, HTTPException
from typing import List
from app.schemas.upload import Upload
from app.services import upload_service
from app.services.upload_service import _safe_segment
from app.auth import get_current_user
from app.database.supabase.client import supabase
from app.repositories import job_repository, upload_repository

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # a real Thai scan in testing was 11.6 MB


router = APIRouter()

@router.get("/jobs/{job_id}/uploads", response_model=List[Upload])
def get_uploads(job_id: str, user = Depends(get_current_user)):
    return upload_service.get_uploads(job_id, user.id)

@router.post("/uploads", response_model=List[Upload])
def create_uploads(uploads: List[Upload], user = Depends(get_current_user)):
    return upload_service.create_uploads(uploads, user.id)

@router.put("/uploads/{upload_id}")
def update_upload(upload_id: str, upload: Upload, user = Depends(get_current_user)):
    upload_service.update_upload(upload_id, upload, user.id)
    return {"status": "success"}

@router.post("/uploads/file")
async def upload_file(
    file: UploadFile = File(...), 
    id: str = Form(...), 
    jobId: str = Form(...), 
    user = Depends(get_current_user)
):
    # Async only for file.read; the blocking Supabase calls go to a worker thread.
    if not await asyncio.to_thread(job_repository.get_job, jobId, user.id):
        raise HTTPException(status_code=404, detail="Job not found")
    if not _safe_segment(id) or not _safe_segment(file.filename or ""):
        raise HTTPException(status_code=400, detail="Invalid upload id or filename")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 20 MB upload limit")
    try:
        file_path = f"{jobId}/{id}_{file.filename}"
        await asyncio.to_thread(supabase.storage.from_("uploads").upload, file_path, content,
                                file_options={"content-type": file.content_type, "x-upsert": "true"})
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/uploads/{upload_id}/download")
def download_file(upload_id: str, user = Depends(get_current_user)):
    try:
        record = upload_repository.get_upload(upload_id)
        # The row's job must be the caller's too: job_id and name are client-supplied and build the path.
        if not record or record["user_id"] != user.id or not job_repository.get_job(record["job_id"], user.id):  # 404, not 403: don't confirm other users' ids
            raise HTTPException(status_code=404, detail="Upload record not found")

        job_id = record["job_id"]
        filename = record["name"]
        file_path = f"{job_id}/{upload_id}_{filename}"
        
        res = supabase.storage.from_("uploads").download(file_path)
        return Response(content=res, media_type="application/octet-stream")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
