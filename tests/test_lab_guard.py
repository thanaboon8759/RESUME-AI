from fastapi import FastAPI
from fastapi.testclient import TestClient

from lab_guard import install_guards


def make_client():
    app = FastAPI()
    install_guards(app)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.post("/api/process")
    def process():
        return {"ran": True}

    return TestClient(app, base_url="http://127.0.0.1:8000")


def test_local_requests_work():
    c = make_client()
    assert c.get("/api/health").status_code == 200
    assert c.post("/api/process", headers={"Origin": "http://127.0.0.1:8000"}).status_code == 200
    assert c.post("/api/process").status_code == 200  # curl and scripts send no Origin


def test_dns_rebinding_host_refused():
    # A rebound attacker domain reaches 127.0.0.1 but keeps its own Host header.
    assert make_client().get("/api/health", headers={"Host": "attacker.example"}).status_code == 400


def test_cross_site_post_refused():
    # A form POST from any website needs no preflight, so CORS alone never stops it running.
    r = make_client().post("/api/process", headers={"Origin": "https://attacker.example"})
    assert r.status_code == 403 and "ran" not in r.text
