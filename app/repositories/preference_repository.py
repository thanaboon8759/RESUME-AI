from app.database.supabase.client import supabase
from app.schemas.preference import Preferences

# Rows used to share the primary key "default", so each save took the row from the previous user.
# Each user's row is now keyed by their user id; a "default" row they still own is read as a fallback.
LEGACY_ID = "default"


def get_preferences(user_id: str) -> Preferences | None:
    if not supabase: return None
    rows = supabase.table("preferences").select("*").eq("user_id", user_id).execute().data or []
    own = [r for r in rows if r["id"] == user_id] or [r for r in rows if r["id"] == LEGACY_ID]
    if not own:
        return None
    data = own[0]
    data["jobDeleted"] = data.get("job_deleted", False)
    return Preferences(**data)


def update_preferences(prefs: Preferences, user_id: str):
    if not supabase: return
    db_record = prefs.model_dump(mode="json")
    db_record["id"] = user_id
    db_record["user_id"] = user_id
    db_record["job_deleted"] = db_record.pop("jobDeleted", False)
    supabase.table("preferences").upsert(db_record).execute()
