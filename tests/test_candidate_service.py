from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.candidate import CandidateCreate, CandidateProfile, PersonalInfo, ScreeningResult
from app.schemas.core import CriterionStatusEnum, DecisionEnum
from app.schemas.job import Job
from app.services.candidate_service import create_candidate

SVC = "app.services.candidate_service"


def make_job():
    return Job(id="job1", title="Dev", jd="", required=["Python"], preferred=[], weights={"Python": 5},
               experience="", education="", location="", salary="", mandatory=["Python"])


async def test_create_candidate_applies_job_rules():
    screening = ScreeningResult(score=90, decision=DecisionEnum.shortlisted, criteria=[
        {"label": "Python", "status": "unmet"}, {"label": "SQL", "status": "met"}])
    profile = CandidateProfile(personal_info=PersonalInfo(name="Ann Lee"))
    save = MagicMock()
    with patch(f"{SVC}.analyze_resume_facts_with_qwen", AsyncMock(return_value=profile)), \
         patch(f"{SVC}.screen_candidate_with_qwen", AsyncMock(return_value=screening)), \
         patch(f"{SVC}.job_repository.get_job", return_value=make_job()), \
         patch(f"{SVC}.candidate_repository.create_candidate", save):
        cand = await create_candidate("job1", CandidateCreate(name="Ann Lee", resume_text="..."), "user1")

    py = next(x for x in cand.criteria if x.label == "Python")
    assert py.weight == 5 and py.mandatory is True
    assert cand.hasBlocker is True and cand.decision == DecisionEnum.rejected
    saved = save.call_args.args[3]  # ai_evaluation passed to repository
    assert saved.decision == DecisionEnum.rejected and saved.score == cand.score


async def test_create_candidate_unknown_job():
    screening = ScreeningResult(score=61, decision=DecisionEnum.shortlisted, criteria=[], reasons=["x"])
    profile = CandidateProfile(personal_info=PersonalInfo(name="Ann Lee"))
    with patch(f"{SVC}.analyze_resume_facts_with_qwen", AsyncMock(return_value=profile)), \
         patch(f"{SVC}.screen_candidate_with_qwen", AsyncMock(return_value=screening)), \
         patch(f"{SVC}.job_repository.get_job", return_value=None), \
         patch(f"{SVC}.candidate_repository.create_candidate", MagicMock()):
        cand = await create_candidate("job1", CandidateCreate(name="Ann Lee", resume_text="..."), "user1")

    assert cand.score == 61 and cand.decision == DecisionEnum.undecided


async def test_fallback_reasons_are_unknown():
    screening = ScreeningResult(score=61, decision=DecisionEnum.shortlisted, criteria=[], reasons=["Lacks SQL"])
    profile = CandidateProfile(personal_info=PersonalInfo(name="Ann Lee"))
    with patch(f"{SVC}.analyze_resume_facts_with_qwen", AsyncMock(return_value=profile)), \
         patch(f"{SVC}.screen_candidate_with_qwen", AsyncMock(return_value=screening)), \
         patch(f"{SVC}.job_repository.get_job", return_value=None), \
         patch(f"{SVC}.candidate_repository.create_candidate", MagicMock()):
        cand = await create_candidate("job1", CandidateCreate(name="Ann Lee", resume_text="..."), "user1")

    assert [x.status for x in cand.criteria] == [CriterionStatusEnum.unknown]


def test_job_row_with_negative_weight_still_loads():
    # job_repository builds Job(**row); an old row must not crash job lists or resume uploads
    assert Job(**{**make_job().model_dump(), "weights": {"Python": -1}}).weights == {"Python": -1}
