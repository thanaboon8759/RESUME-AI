from typing import List
from app.database.supabase.client import supabase
from app.schemas.decision import Decision

def get_decisions(user_id: str) -> List[Decision]:
    if not supabase: return []
    res = supabase.table("decisions").select("*").eq("user_id", user_id).execute()
    return [Decision(
        id=r["id"], candidateId=r["candidate_id"], reasonCode=r["reason_code"],
        jobId=r["job_id"], at=r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else r["created_at"], actor=r["actor"],
        reasonLabel=r["reason_label"], candidateName=r["candidate_name"],
        decision=r["decision"], note=r.get("note"), secondsSpent=r.get("seconds_spent")
    ) for r in res.data]

def create_decision(decision: Decision, user_id: str):
    if not supabase: return
    db_record = {
        "candidate_id": decision.candidateId, "user_id": user_id, "job_id": decision.jobId, "reason_code": decision.reasonCode,
        "reason_label": decision.reasonLabel, "decision": decision.decision.value if hasattr(decision.decision, "value") else decision.decision, 
        "actor": decision.actor, "candidate_name": decision.candidateName,
        "note": decision.note, "seconds_spent": decision.secondsSpent
    }
    supabase.table("decisions").insert(db_record).execute()

def clear_decisions(job_id: str, user_id: str):
    if not supabase: return
    supabase.table("decisions").delete().eq("job_id", job_id).eq("user_id", user_id).execute()
