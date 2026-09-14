from fastapi import APIRouter, HTTPException, Depends
from app.schemas.preference import Preferences
from app.services import preference_service
from app.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=Preferences)
async def get_preferences(user = Depends(get_current_user)):
    prefs = preference_service.get_preferences(user.id)
    if not prefs:
        prefs = Preferences(
            name="Workspace",
            email=user.email,
            company="My Company",
            retention="0",
            reasons={"0": "ประสบการณ์ทำงานน้อยไป", "1": "เรียกเงินเดือนสูงเกินไป", "2": "ทักษะไม่ตรงกับตำแหน่ง", "3": "อื่นๆ"},
            members=[{"id": "owner", "email": user.email, "role": "admin"}],
            deleted=[],
            jobDeleted=False
        )
        preference_service.update_preferences(prefs, user.id)
    return prefs

@router.put("/", response_model=Preferences)
async def update_preferences(prefs: Preferences, user = Depends(get_current_user)):
    return preference_service.update_preferences(prefs, user.id)
