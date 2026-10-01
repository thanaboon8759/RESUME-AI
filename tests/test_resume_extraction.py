import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.resume_extraction_service import analyze_resume_facts_with_qwen
from app.schemas.candidate import CandidateProfile
import json

VALID_PROFILE_JSON = '''{
    "personal_info": {"name": "Test Candidate", "email": "real@example.com", "phone": "555-1234", "location": "Bangkok", "website": null, "github": null, "linkedin": null},
    "education": [{"institution": "Bangkok University", "degree": "BS", "dates": "2020"}],
    "experience": [{"company": "ABC Corp", "position": "Developer", "dates": "2021-2022", "responsibilities": ["Coding"]}],
    "projects": [{"title": "AI Project", "description": "Did AI", "technologies": ["Python"]}],
    "skills": [{"name": "Python", "evidence": {"quote": "Python", "block_ids": ["b1"]}}, {"name": "AWS", "evidence": {"quote": "AWS", "block_ids": ["b2"]}}],
    "certifications": [],
    "languages": ["English", "Thai"]
}'''

@pytest.fixture
def mock_qwen():
    with patch('app.services.resume_extraction_service.qwen_client.chat.completions.create', new_callable=AsyncMock) as mock:
        mock.return_value.choices = [MagicMock(message=MagicMock(content=VALID_PROFILE_JSON))]
        yield mock

@pytest.mark.asyncio
async def test_qwen_extracts_facts_only(mock_qwen):
    profile = await analyze_resume_facts_with_qwen("resume text", "Test Candidate")
    
    # Verify it returns a CandidateProfile
    assert isinstance(profile, CandidateProfile)
    # Verify factual fields
    assert profile.personal_info.email == "real@example.com"
    assert profile.personal_info.phone == "555-1234"
    assert profile.personal_info.location == "Bangkok"
    
    # Ensure there is NO score or decision (these properties don't even exist on CandidateProfile)
    assert not hasattr(profile, "score")
    assert not hasattr(profile, "decision")

@pytest.mark.asyncio
async def test_qwen_handles_invalid_json():
    with patch('app.services.resume_extraction_service.qwen_client.chat.completions.create', new_callable=AsyncMock) as mock:
        mock.return_value.choices = [MagicMock(message=MagicMock(content="{ invalid json }"))]
        
        with pytest.raises(Exception, match="AI processing error"):
            await analyze_resume_facts_with_qwen("resume text", "Test Candidate")

@pytest.mark.asyncio
async def test_qwen_handles_missing_fields(mock_qwen):
    MISSING_FIELDS_JSON = '''{
        "personal_info": {"name": "Test Candidate", "email": null, "phone": null, "location": null, "website": null, "github": null, "linkedin": null},
        "education": [],
        "experience": [],
        "projects": [],
        "skills": [],
        "certifications": [],
        "languages": []
    }'''
    mock_qwen.return_value.choices = [MagicMock(message=MagicMock(content=MISSING_FIELDS_JSON))]
    
    profile = await analyze_resume_facts_with_qwen("Email: Phone: Address:", "Test Candidate")
    
    # Ensure placeholders became null
    assert profile.personal_info.email is None
    assert profile.personal_info.phone is None
    assert len(profile.education) == 0
    assert len(profile.experience) == 0
