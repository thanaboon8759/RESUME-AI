import io
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from app.schemas.candidate import CandidateProfile, PersonalInfo
from app.schemas.job import Job
from app.services import ai_config, document_extraction_service as docs
from app.services import resume_extraction_service, screening_service


def image_pdf():
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(buf, "PDF")
    return buf.getvalue()


def make_job():
    return Job(id="job1", title="Dev", jd="", required=["Python"], preferred=[], weights={}, experience="",
               education="", location="", salary="", mandatory=[])


def test_missing_key_raises():
    with pytest.raises(RuntimeError, match="DASHSCOPE_API_KEY is not set"):
        ai_config.mock_mode(None, "DASHSCOPE_API_KEY")


def test_empty_key_raises():
    with pytest.raises(RuntimeError, match="X is not set"):
        ai_config.mock_mode("", "X")


def test_mock_value_still_mocks():
    assert ai_config.mock_mode("mock", "X") is True
    assert ai_config.mock_mode("sk-real", "X") is False


async def test_extraction_without_key_raises(monkeypatch):
    # Before: a missing key silently returned "Mock University" as if it were the candidate's real profile.
    monkeypatch.setattr(ai_config, "DASHSCOPE_API_KEY", None)
    with pytest.raises(RuntimeError, match="DASHSCOPE_API_KEY"):
        await resume_extraction_service.analyze_resume_facts_with_qwen("text", "Ann")


async def test_screening_without_key_raises(monkeypatch):
    monkeypatch.setattr(ai_config, "DASHSCOPE_API_KEY", None)
    profile = CandidateProfile(personal_info=PersonalInfo(name="Ann"))
    with pytest.raises(RuntimeError, match="DASHSCOPE_API_KEY"):
        await screening_service.screen_candidate_with_qwen(profile, make_job())


async def test_typhoon_without_key_raises(monkeypatch):
    monkeypatch.setattr(docs, "TYPHOON_API_KEY", None)
    with pytest.raises(RuntimeError, match="TYPHOON_API_KEY"):
        await docs.extract_text_typhoon(b"%PDF")


async def test_local_ocr_needs_no_typhoon_key(monkeypatch):
    monkeypatch.setattr(docs, "TYPHOON_API_KEY", None)
    monkeypatch.setenv("OCR_PROVIDER", "ollama")
    monkeypatch.setattr(docs, "extract_text_local", AsyncMock(return_value="local"))
    assert (await docs.extract_document(image_pdf()))[0] == "local"


def test_services_share_one_client():
    assert resume_extraction_service.qwen_client is screening_service.qwen_client is ai_config.qwen_client
