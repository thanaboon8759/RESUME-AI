import pytest


@pytest.fixture(autouse=True)
def fake_qwen_key(monkeypatch):
    # The app refuses to run without an AI key; tests mock every AI call, so give them a dummy one.
    # Tests about a missing key set it to None themselves.
    from app.services import ai_config
    monkeypatch.setattr(ai_config, "DASHSCOPE_API_KEY", "test-key")
