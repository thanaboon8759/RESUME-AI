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
