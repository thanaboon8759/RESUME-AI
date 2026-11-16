from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import get_current_user
from app.main import app

DECISION = {"id": "d1", "candidateId": "c1", "reasonCode": "r", "jobId": "j1", "at": "2026-11-16T00:00:00Z",
            "actor": "hr", "reasonLabel": "ok", "candidateName": "Ann", "decision": "shortlisted"}


class MockUser:
    id = "u1"
    email = "test@example.com"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: MockUser())
    save = MagicMock()
    monkeypatch.setattr("app.repositories.decision_repository.create_decision", save)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test"), save


def set_candidate(monkeypatch, job_id):
    monkeypatch.setattr("app.repositories.candidate_repository.get_candidate_job_id",
                        lambda candidate_id, user_id: job_id)


async def test_decision_on_foreign_candidate_is_404(monkeypatch, client):
    ac, save = client
    set_candidate(monkeypatch, None)
    assert (await ac.post("/api/decisions/", json=DECISION)).status_code == 404
    save.assert_not_called()


async def test_decision_on_own_candidate_saved(monkeypatch, client):
    ac, save = client
    set_candidate(monkeypatch, "j1")
    assert (await ac.post("/api/decisions/", json=DECISION)).status_code == 200
    save.assert_called_once()


async def test_decision_job_comes_from_candidate(monkeypatch, client):
    # The client's jobId used to be stored as sent, so a decision could be filed under the wrong job.
    ac, save = client
    set_candidate(monkeypatch, "j-real")
    assert (await ac.post("/api/decisions/", json={**DECISION, "jobId": "j-other"})).status_code == 200
    assert save.call_args.args[0].jobId == "j-real"
