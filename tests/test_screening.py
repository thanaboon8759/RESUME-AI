import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.screening_service import screen_candidate_with_qwen
from app.schemas.candidate import CandidateProfile, ScreeningResult, PersonalInfo
from app.schemas.job import Job
from app.schemas.core import DecisionEnum
import json

VALID_SCREENING_JSON = '''{
    "score": 90,
    "decision": "shortlisted",
    "role": "Developer",
    "headline": "Great Match",
    "experience_summary": "5 years",
    "location": "Bangkok",
    "strengths": ["Python is required and present"],
    "weaknesses": ["Missing AWS"],
    "missingInformation": [],
    "detectedLanguages": ["English"],
    "reasons": ["Good fit based on criteria"],
    "criteria": [
        {"label": "Python", "status": "met", "evidence_refs": [{"field": "skills", "value": "Python"}]}
    ]
}'''

@pytest.fixture
def mock_qwen_screening():
    with patch('app.services.screening_service.qwen_client.chat.completions.create', new_callable=AsyncMock) as mock:
        mock.return_value.choices = [MagicMock(message=MagicMock(content=VALID_SCREENING_JSON))]
        yield mock

@pytest.fixture
def dummy_profile():
    return CandidateProfile(
        personal_info=PersonalInfo(name="Test Candidate", email="real@example.com"),
        education=[],
        experience=[],
        projects=[],
        skills=[{"name": "Python", "evidence": {"quote": "Python 5 years", "block_ids": ["b1"]}}],
        certifications=[],
        languages=[]
    )

@pytest.fixture
def dummy_job():
    return Job(
        id="job1", title="Developer", jd="", required=["Python"], preferred=["AWS"], 
        weights={"Python": 5}, experience="3", education="BS", location="Bangkok", salary="100k", mandatory=["Python"]
    )

@pytest.mark.asyncio
async def test_qwen_screens_candidate(mock_qwen_screening, dummy_profile, dummy_job):
    result = await screen_candidate_with_qwen(dummy_profile, dummy_job)
    
    # Verify it returns a ScreeningResult
    assert isinstance(result, ScreeningResult)
    # Verify screening fields
    assert result.score == 90
    assert result.decision == DecisionEnum.shortlisted
    assert len(result.criteria) == 1
    assert result.criteria[0].label == "Python"
    assert result.criteria[0].status.value == "met"

@pytest.mark.asyncio
async def test_qwen_handles_invalid_json_screening(dummy_profile, dummy_job):
    with patch('app.services.screening_service.qwen_client.chat.completions.create', new_callable=AsyncMock) as mock:
        mock.return_value.choices = [MagicMock(message=MagicMock(content="{ invalid json }"))]
        
        with pytest.raises(Exception, match="AI screening error"):
            await screen_candidate_with_qwen(dummy_profile, dummy_job)
