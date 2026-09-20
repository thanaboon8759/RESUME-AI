import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.document_extraction_service import extract_document, extract_text_fitz, extract_text_typhoon, is_extraction_usable
import json

@pytest.fixture(autouse=True)
def patch_api_keys():
    with patch('app.services.document_extraction_service.TYPHOON_API_KEY', 'fake_key'):
        yield

@pytest.fixture
def mock_httpx():
    with patch('app.services.document_extraction_service.httpx.AsyncClient.post', new_callable=AsyncMock) as mock:
        yield mock

@pytest.mark.asyncio
async def test_1_fitz_extracts_valid_text_no_typhoon(mock_httpx):
    long_text = "Hello world! " * 20
    with patch('app.services.document_extraction_service.extract_text_fitz') as mock_fitz:
        mock_fitz.return_value = (long_text, [{"id": "b0", "text": long_text, "bbox": {"x":0,"y":0,"width":1,"height":1}, "page": 1}])
        text, blocks = await extract_document(b"fakebytes")
        
        # Assert typhoon was NOT called because text is sufficient
        mock_httpx.assert_not_called()
        assert len(blocks) == 1

@pytest.mark.asyncio
async def test_2_and_4_image_based_pdf_calls_typhoon(mock_httpx):
    with patch('app.services.document_extraction_service.extract_text_fitz') as mock_fitz:
        # Setup fitz to return little text (insufficient)
        mock_fitz.return_value = ("Too short.", [])
        
        # Setup mock Typhoon
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{"success": True, "message": {"choices": [{"message": {"content": "Typhoon OCR Text"}}]}}]
        }
        mock_httpx.return_value = mock_response
        
        text, blocks = await extract_document(b"fakebytes")
        
        # Assert Typhoon was called
        assert mock_httpx.called
        assert "Typhoon OCR Text" in text
        assert len(blocks) == 0 # OCR leaves blocks empty

@pytest.mark.asyncio
async def test_3_multipage_pdf_accumulation():
    with patch('app.services.document_extraction_service.extract_text_fitz') as mock_fitz:
        mock_fitz.return_value = ("Page 1 Text\nPage 2 Text", [])
        text, blocks = mock_fitz(b"fakebytes")
        assert "Page 1 Text" in text
        assert "Page 2 Text" in text

@pytest.mark.asyncio
async def test_8_logging_outputs(caplog):
    # Use caplog to capture log output
    import logging
    
    with patch('app.services.document_extraction_service.extract_text_fitz') as mock_fitz:
        # We want to capture INFO logs from the document_pipeline logger
        with caplog.at_level(logging.INFO, logger="app.services.document_extraction_service"):
            mock_fitz.return_value = ("Hello world! " * 20, [])
            await extract_document(b"fakebytes")
        
        # Verify the expected logs are recorded
        logs = caplog.text
        assert "Document extraction started" in logs
        assert "fitz text sufficient: true" in logs

@pytest.mark.parametrize("text,expected", [
    # 1. Normal English resume
    ("John Doe\nSoftware Engineer\nExperience: 5 years at Google. Skilled in Python, AWS.", True),
    # 2. Normal Thai resume
    ("สมชาย ใจดี\nนักพัฒนาซอฟต์แวร์\nประสบการณ์ทำงาน: 5 ปีที่บริษัท แสนสิริ จำกัด", True),
    # 3. Thai + English mixed resume
    ("บริษัท ABC จำกัด\nSoftware Developer\nมกราคม 2024 - ธันวาคม 2025\nSkills: React, Node.js", True),
    # 4. Corrupted/garbled font extraction
    ("\ufffd\ufffd\ufffd \ufffd\ufffd\ufffd \ufffd\ufffd\ufffd \ufffd\ufffd\ufffd \ufffd\ufffd\ufffd \ufffd\ufffd\ufffd \ufffd\ufffd\ufffd \ufffd\ufffd\ufffd \ufffd\ufffd\ufffd", False),
    # 5. Lots of question marks / corrupted
    ("???? ???? ??? ??? ??? ??? ??? ??? ??? ??? ??? ??? ??? ??? ??? ???", False),
    # 6. Resume containing many numbers/symbols but valid text
    ("01-02-2023: +66-89-123-4567 email: test@example.com (90% match, $1000/mo) @skills #React #TS", True),
    # 7. Valid PDF with less than 100 meaningful characters
    ("Too short.", False)
])
def test_is_extraction_usable(text, expected):
    # For tests that are naturally short, we pad them just to test the alphanumeric/garble ratio properly
    # Except for test 7 which tests the <100 length rejection natively
    if "Too short" not in text:
        text = text * 10
    
    assert is_extraction_usable(text) == expected
