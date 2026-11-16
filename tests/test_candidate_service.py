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
    # A missing job used to get a fake "Unknown Job": two paid AI calls, then the save failed on the job foreign key.
    import pytest
    from fastapi import HTTPException
    extract, screen = AsyncMock(), AsyncMock()
    with patch(f"{SVC}.analyze_resume_facts_with_qwen", extract), patch(f"{SVC}.screen_candidate_with_qwen", screen),          patch(f"{SVC}.job_repository.get_job", return_value=None), pytest.raises(HTTPException) as err:
        await create_candidate("job1", CandidateCreate(name="Ann Lee", resume_text="..."), "user1")
    assert err.value.status_code == 404
    extract.assert_not_called()
    screen.assert_not_called()


async def test_fallback_reasons_are_unknown():
    screening = ScreeningResult(score=61, decision=DecisionEnum.shortlisted, criteria=[], reasons=["Lacks SQL"])
    profile = CandidateProfile(personal_info=PersonalInfo(name="Ann Lee"))
    with patch(f"{SVC}.analyze_resume_facts_with_qwen", AsyncMock(return_value=profile)), \
         patch(f"{SVC}.screen_candidate_with_qwen", AsyncMock(return_value=screening)), \
         patch(f"{SVC}.job_repository.get_job", return_value=make_job()), \
         patch(f"{SVC}.candidate_repository.create_candidate", MagicMock()):
        cand = await create_candidate("job1", CandidateCreate(name="Ann Lee", resume_text="..."), "user1")

    assert [x.status for x in cand.criteria] == [CriterionStatusEnum.unknown]


def test_job_row_with_negative_weight_still_loads():
    # job_repository builds Job(**row); an old row must not crash job lists or resume uploads
    assert Job(**{**make_job().model_dump(), "weights": {"Python": -1}}).weights == {"Python": -1}


async def _create_with_url(resume_url, job):
    import pytest
    from fastapi import HTTPException
    storage = MagicMock()
    with patch(f"{SVC}.supabase", storage), patch(f"{SVC}.job_repository.get_job", return_value=job), \
         pytest.raises(HTTPException) as err:
        await create_candidate("job1", CandidateCreate(name="Ann", resume_text="", resume_url=resume_url), "user1")
    storage.storage.from_.return_value.download.assert_not_called()
    return err.value


async def test_resume_from_other_job_is_404():
    assert (await _create_with_url("otherjob/x_a.pdf", make_job())).status_code == 404


async def test_resume_for_unowned_job_is_404():
    assert (await _create_with_url("job1/x_a.pdf", None)).status_code == 404


async def test_text_only_candidate_skips_ownership():
    screening = ScreeningResult(score=61, decision=DecisionEnum.shortlisted, criteria=[], reasons=["x"])
    profile = CandidateProfile(personal_info=PersonalInfo(name="Ann Lee"))
    with patch(f"{SVC}.analyze_resume_facts_with_qwen", AsyncMock(return_value=profile)), \
         patch(f"{SVC}.screen_candidate_with_qwen", AsyncMock(return_value=screening)), \
         patch(f"{SVC}.job_repository.get_job", return_value=make_job()), \
         patch(f"{SVC}.candidate_repository.create_candidate", MagicMock()):
        cand = await create_candidate("job1", CandidateCreate(name="Ann Lee", resume_text="...", resume_url=None), "user1")
    assert cand.name == "Ann Lee"  # a text-only resume needs no storage path, only an owned job


async def test_resume_path_traversal_is_404():
    assert (await _create_with_url("job1/../otherjob/x_a.pdf", make_job())).status_code == 404


async def test_resume_path_percent_traversal_is_404():
    assert (await _create_with_url("job1/%2E%2E/otherjob/x_a.pdf", make_job())).status_code == 404


def test_position_is_the_candidates_role():
    # Every row used to say "Backend Developer", whatever the job was.
    from app.repositories import candidate_repository
    screening = ScreeningResult(score=50, decision=DecisionEnum.undecided, criteria=[])
    rich = MagicMock(role="Product Designer")
    rich.model_dump.return_value = {}
    sb = MagicMock()
    with patch("app.repositories.candidate_repository.supabase", sb):
        candidate_repository.create_candidate("c1", "job1", "Ann", screening, rich, "u1")
    assert sb.table.return_value.insert.call_args.args[0]["position"] == "Product Designer"
