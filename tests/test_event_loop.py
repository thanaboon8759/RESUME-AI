import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.candidate import CandidateCreate, CandidateProfile, PersonalInfo, ScreeningResult
from app.schemas.core import DecisionEnum
from app.schemas.job import Job
from app.services.candidate_service import create_candidate

# These routes only make blocking Supabase calls. As plain `def` routes FastAPI runs them in its threadpool;
# as `async def` they would block the one event loop that serves every user.
SYNC_ROUTES = {"get_jobs", "create_job", "update_job", "get_job_candidates", "get_candidate",
               "download_candidate_resume", "get_decisions", "create_decision", "clear_decisions",
               "get_preferences", "update_preferences", "get_uploads", "create_uploads", "update_upload",
               "download_file"}
SVC = "app.services.candidate_service"


def test_sync_routes_run_in_threadpool():
    from app.api import candidates, decisions, jobs, preferences, uploads
    # Read the routers themselves: this FastAPI version wraps included routers, so app.routes hides them.
    routes = [r for module in (candidates, decisions, jobs, preferences, uploads) for r in module.router.routes]
    found = {r.endpoint.__name__: r.endpoint for r in routes if r.endpoint.__name__ in SYNC_ROUTES}
    assert set(found) == SYNC_ROUTES
    assert [name for name, fn in found.items() if inspect.iscoroutinefunction(fn)] == []


async def test_create_candidate_offloads_blocking_calls(monkeypatch):
    offloaded, real = [], asyncio.to_thread

    async def spy(fn, *args, **kwargs):
        offloaded.append(fn)
        return await real(fn, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", spy)
    job = Job(id="job1", title="Dev", jd="", required=[], preferred=[], weights={}, experience="",
              education="", location="", salary="", mandatory=[])
    storage = MagicMock()
    download = storage.storage.from_.return_value.download
    download.return_value = b"%PDF"
    get_job, save = MagicMock(return_value=job), MagicMock()
    screening = ScreeningResult(score=50, decision=DecisionEnum.undecided, criteria=[])
    with patch(f"{SVC}.supabase", storage), patch(f"{SVC}.job_repository.get_job", get_job), \
         patch(f"{SVC}.candidate_repository.create_candidate", save), \
         patch(f"{SVC}.extract_document", AsyncMock(return_value=("text", []))), \
         patch(f"{SVC}.analyze_resume_facts_with_qwen",
               AsyncMock(return_value=CandidateProfile(personal_info=PersonalInfo(name="Ann")))), \
         patch(f"{SVC}.screen_candidate_with_qwen", AsyncMock(return_value=screening)):
        await create_candidate("job1", CandidateCreate(name="Ann", resume_text="", resume_url="job1/x_a.pdf"), "u1")
    assert get_job in offloaded and download in offloaded and save in offloaded
