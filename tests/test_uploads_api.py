from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import uploads as api
from app.auth import get_current_user
from app.main import app


class MockUser:
    id = "u1"
    email = "test@example.com"


OTHER = {"id": "x", "job_id": "j", "user_id": "someone-else", "name": "a.pdf"}
OWN = {**OTHER, "user_id": "u1"}


@pytest.fixture
def storage(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: MockUser()
    sb = MagicMock()
    monkeypatch.setattr(api, "supabase", sb)
    yield sb.storage.from_.return_value
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def set_upload(monkeypatch, row):
    monkeypatch.setattr("app.repositories.upload_repository.get_upload", lambda upload_id: row, raising=False)


def set_job(monkeypatch, job):
    monkeypatch.setattr("app.repositories.job_repository.get_job", lambda job_id, user_id: job)


async def post_file(client, name="cv.pdf", content=b"%PDF", upload_id="x"):
    return await client.post("/api/uploads/file", files={"file": (name, content, "application/pdf")},
                             data={"id": upload_id, "jobId": "j"})


async def test_download_other_users_upload_is_404(monkeypatch, storage, client):
    set_upload(monkeypatch, OTHER)
    r = await client.get("/api/uploads/x/download")
    assert r.status_code == 404
    storage.download.assert_not_called()


async def test_download_own_upload(monkeypatch, storage, client):
    set_upload(monkeypatch, OWN)
    storage.download.return_value = b"%PDF"
    r = await client.get("/api/uploads/x/download")
    assert r.status_code == 200 and r.content == b"%PDF"
    storage.download.assert_called_once_with("j/x_a.pdf")


async def test_download_missing_is_404(monkeypatch, storage, client):
    set_upload(monkeypatch, None)
    assert (await client.get("/api/uploads/x/download")).status_code == 404


async def test_upload_to_other_users_job_is_404(monkeypatch, storage, client):
    set_job(monkeypatch, None)
    assert (await post_file(client)).status_code == 404
    storage.upload.assert_not_called()


async def test_upload_rejects_path_segments(monkeypatch, storage, client):
    set_job(monkeypatch, object())
    assert (await post_file(client, name="../x.pdf")).status_code == 400
    assert (await post_file(client, upload_id="a/b")).status_code == 400
    assert (await post_file(client, upload_id="..")).status_code == 400
    assert (await post_file(client, upload_id="a\\b")).status_code == 400
    storage.upload.assert_not_called()


async def test_thai_filename_allowed(monkeypatch, storage, client):
    set_job(monkeypatch, object())
    assert (await post_file(client, name="เรซูเม่.pdf")).status_code == 200
    assert storage.upload.call_args.args[0] == "j/x_เรซูเม่.pdf"


async def test_upload_size_limit(monkeypatch, storage, client):
    set_job(monkeypatch, object())
    monkeypatch.setattr(api, "MAX_UPLOAD_BYTES", 10, raising=False)
    assert (await post_file(client, content=b"x" * 10)).status_code == 200
    assert (await post_file(client, content=b"x" * 11)).status_code == 413
    assert storage.upload.call_count == 1


def body(upload_id):
    return {"id": upload_id, "jobId": "j", "name": "a.pdf", "size": 1, "status": "queued", "reason": "", "attempts": 0}


@pytest.fixture
def saved(monkeypatch):
    save = MagicMock()
    monkeypatch.setattr("app.repositories.upload_repository.update_upload", save)
    return save


async def test_update_other_users_row_is_404(monkeypatch, storage, client, saved):
    set_upload(monkeypatch, OTHER)
    assert (await client.put("/api/uploads/x", json=body("x"))).status_code == 404
    saved.assert_not_called()


async def test_update_creates_new_row(monkeypatch, storage, client, saved):
    set_upload(monkeypatch, None)
    assert (await client.put("/api/uploads/x", json=body("x"))).status_code == 200
    saved.assert_called_once()


async def test_update_uses_path_id(monkeypatch, storage, client, saved):
    set_upload(monkeypatch, OWN)
    assert (await client.put("/api/uploads/x", json=body("y"))).status_code == 200
    assert saved.call_args.args[0].id == "x"
