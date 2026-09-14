import uuid
from typing import List
from app.schemas.candidate import Candidate, CandidateCreate
from app.schemas.core import CriterionStatusEnum
from app.repositories import candidate_repository
# Move the import of dumbdog_service logic here!
from app.services.dumbdog_service import dumbdog_client

def get_candidates(job_id: str, user_id: str) -> List[Candidate]:
    return candidate_repository.get_candidates_for_job(job_id, user_id)

def get_candidate(candidate_id: str, user_id: str) -> Candidate | None:
    return candidate_repository.get_candidate(candidate_id, user_id)

async def create_candidate(job_id: str, candidate_data: CandidateCreate, user_id: str) -> Candidate:
    ai_evaluation = await dumbdog_client.evaluate_candidate(
        candidate_name=candidate_data.name, position="Backend Developer", resume_text=candidate_data.resume_text
    )

    candidate_id = str(uuid.uuid4())
    criteria = []
    for i, reason in enumerate(ai_evaluation.reasons):
        criteria.append({
            "id": f"crit-{i}", "label": reason, "status": CriterionStatusEnum.met,
            "weight": 3, "mandatory": False, "evidence": []
        })
    rich_candidate = Candidate(
        id=candidate_id, name=candidate_data.name, englishName=candidate_data.name,
        initials="".join([n[0] for n in candidate_data.name.split() if n]), role="Unknown", headline="Evaluated by DumbdogAI",
        score=ai_evaluation.score, experience="Unknown", location="Unknown", resumeUrl="",
        extractedText=candidate_data.resume_text, parseStatus="done", failureReason=None, hasBlocker=False, duplicateOf=None,
        criteria=criteria, strengths=ai_evaluation.reasons, weaknesses=[], missingInformation=[], detectedLanguages=["Thai", "English"],
        decision=ai_evaluation.decision
    )
    
    candidate_repository.create_candidate(candidate_id, job_id, candidate_data.name, ai_evaluation, rich_candidate, user_id)
    return rich_candidate
