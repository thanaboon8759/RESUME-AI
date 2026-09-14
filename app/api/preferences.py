from fastapi import APIRouter, HTTPException, Depends
from app.schemas.preference import Preferences
from app.services import preference_service
from app.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=Preferences)
async def get_preferences(user = Depends(get_current_user)):
    prefs = preference_service.get_preferences(user.id)
    if not prefs:
        display_name = (user.user_metadata or {}).get("displayName") or (user.email.split('@')[0] if user.email else "Workspace")
        default_reasons = [
            {"id": "reason-0-0", "label": "ผลงานตรงกับที่ต้องการ", "appliesTo": ["shortlisted"], "hidden": False, "isDefault": True},
            {"id": "reason-1-0", "label": "ประสบการณ์ไม่ตรงสายงาน", "appliesTo": ["rejected"], "hidden": False, "isDefault": True},
            {"id": "reason-1-1", "label": "ขาดทักษะหลัก", "appliesTo": ["rejected"], "hidden": False, "isDefault": True},
            {"id": "reason-2-0", "label": "ต้องการข้อมูลเพิ่มเติม", "appliesTo": ["undecided"], "hidden": False, "isDefault": True}
        ]
            
        prefs = Preferences(
            name=display_name,
            email=user.email,
            company="",
            retention="0",
            reasons=default_reasons,
            members=[{"id": "owner", "email": user.email, "role": "user"}],
            deleted=[],
            jobDeleted=False
        )
        preference_service.update_preferences(prefs, user.id)
    return prefs

@router.put("/", response_model=Preferences)
async def update_preferences(prefs: Preferences, user = Depends(get_current_user)):
    return preference_service.update_preferences(prefs, user.id)
