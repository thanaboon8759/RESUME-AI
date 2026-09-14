from fastapi import APIRouter, Depends, UploadFile, File, Form, Response, HTTPException
from typing import List
from app.schemas.upload import Upload
from app.services import upload_service
from app.auth import get_current_user
from app.database.supabase.client import supabase

router = APIRouter()

@router.get("/jobs/{job_id}/uploads", response_model=List[Upload])
async def get_uploads(job_id: str, user = Depends(get_current_user)):
    return upload_service.get_uploads(job_id, user.id)

@router.post("/uploads", response_model=List[Upload])
async def create_uploads(uploads: List[Upload], user = Depends(get_current_user)):
    return upload_service.create_uploads(uploads, user.id)

@router.put("/uploads/{upload_id}")
async def update_upload(upload_id: str, upload: Upload, user = Depends(get_current_user)):
    upload_service.update_upload(upload_id, upload, user.id)
    return {"status": "success"}

@router.post("/uploads/file")
async def upload_file(
    file: UploadFile = File(...), 
    id: str = Form(...), 
    jobId: str = Form(...), 
    user = Depends(get_current_user)
):
    try:
        content = await file.read()
        file_path = f"{jobId}/{id}_{file.filename}"
        supabase.storage.from_("uploads").upload(file_path, content)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/uploads/{upload_id}/download")
async def download_file(upload_id: str, user = Depends(get_current_user)):
    try:
        # Find upload record to get the job_id and filename
        record = supabase.table("uploads").select("job_id", "name").eq("id", upload_id).single().execute()
        if not record.data:
            raise HTTPException(status_code=404, detail="Upload record not found")
        
        job_id = record.data["job_id"]
        filename = record.data["name"]
        file_path = f"{job_id}/{upload_id}_{filename}"
        
        res = supabase.storage.from_("uploads").download(file_path)
        return Response(content=res, media_type="application/octet-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
