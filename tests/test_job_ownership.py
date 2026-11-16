from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import get_current_user
from app.main import app

JOB = {"id": "j1", "title": "Dev", "jd": "", "required": [], "preferred": [], "weights": {}, "experience": "",
       "education": "", "location": "", "salary": "", "mandatory": []}


class MockUser:
    id = "u1"
    email = "test@example.com"


@pytest.fixture
def client(monkeypatch):
    # setitem restores test_jobs.py's module-level override afterwards instead of deleting it
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: MockUser())
    save = MagicMock()
    monkeypatch.setattr("app.repositories.job_repository.update_job", save)
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test"), save


def set_owner(monkeypatch, owner):
    monkeypatch.setattr("app.repositories.job_repository.get_job_owner", lambda job_id: owner, raising=False)


async def test_update_other_users_job_is_404(monkeypatch, client):
    ac, save = client
    set_owner(monkeypatch, "someone-else")
    assert (await ac.put("/api/jobs/j1", json=JOB)).status_code == 404
    save.assert_not_called()


async def test_update_own_job(monkeypatch, client):
    ac, save = client
    set_owner(monkeypatch, "u1")
    assert (await ac.put("/api/jobs/j1", json=JOB)).status_code == 200
    save.assert_called_once()


async def test_update_creates_missing_job(monkeypatch, client):
    ac, save = client
    set_owner(monkeypatch, None)
    assert (await ac.put("/api/jobs/j1", json=JOB)).status_code == 200
    save.assert_called_once()


@pytest.fixture
def created(monkeypatch):
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: MockUser())
    save = MagicMock()
    monkeypatch.setattr("app.repositories.job_repository.create_job", save)
    monkeypatch.setattr("app.repositories.candidate_repository.clone_candidates_for_job", MagicMock())
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test"), save


async def test_create_job_rejects_path_ids(created):
    # The job id is the first folder of every storage path: "victimJob/x" would nest inside another user's folder.
    ac, save = created
    for bad in ("a/b", "%2E%2E"):
        assert (await ac.post("/api/jobs/", json={**JOB, "id": bad})).status_code == 400, bad
    save.assert_not_called()


async def test_create_job_accepts_normal_ids(created):
    ac, save = created
    for good in ("design", "3f2b8c1e-0d4a-4c1b-9a77-2f0e5d6c7b8a", "งาน-1"):
        assert (await ac.post("/api/jobs/", json={**JOB, "id": good})).status_code == 200, good
    assert save.call_count == 3


def test_update_job_rejects_path_ids(monkeypatch):
    from fastapi import HTTPException
    from app.schemas.job import Job
    from app.services import job_service
    save = MagicMock()
    monkeypatch.setattr("app.repositories.job_repository.update_job", save)
    monkeypatch.setattr("app.repositories.job_repository.get_job_owner", lambda job_id: None)
    with pytest.raises(HTTPException) as err:
        job_service.update_job("a/b", Job(**JOB), "u1")
    assert err.value.status_code == 400
    save.assert_not_called()
