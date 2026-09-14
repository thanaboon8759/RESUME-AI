from app.database.supabase.client import supabase
from app.schemas.preference import Preferences

def get_preferences(user_id: str) -> Preferences | None:
    if not supabase: return None
    res = supabase.table("preferences").select("*").eq("id", "default").eq("user_id", user_id).execute()
    if res.data:
        data = res.data[0]
        data["jobDeleted"] = data.get("job_deleted", False)
        return Preferences(**data)
    return None

def update_preferences(prefs: Preferences, user_id: str):
    if not supabase: return
    db_record = prefs.model_dump(mode="json")
    db_record["id"] = "default"
    db_record["user_id"] = user_id
    db_record["job_deleted"] = db_record.pop("jobDeleted", False)
    supabase.table("preferences").upsert(db_record).execute()
