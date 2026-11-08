import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

from app.services import document_extraction_service as svc


def image_pdf(pages=2):
    images = [Image.new("RGB", (400, 300), "white") for _ in range(pages)]
    buf = io.BytesIO()
    images[0].save(buf, "PDF", save_all=True, append_images=images[1:])
    return buf.getvalue()


def reply(content, done_reason="stop"):
    r = MagicMock()
    r.json.return_value = {"message": {"content": content}, "done_reason": done_reason}
    r.raise_for_status.return_value = None
    return r


async def test_local_ocr_joins_pages_in_order():
    post = AsyncMock(side_effect=[reply("page1"), reply("page2")])
    with patch("httpx.AsyncClient.post", post):
        text = await svc.extract_text_local(image_pdf(2))
    assert text == "page1\npage2"
    assert post.call_count == 2
    body = post.call_args_list[0].kwargs["json"]
    assert body["stream"] is False and body["messages"][0]["images"]
    assert body["messages"][0]["content"].startswith("Transcribe this resume exactly into plain text.")
    assert body["options"] == {"temperature": 0, "num_ctx": 8192, "num_predict": 4096}


async def test_local_ocr_unwraps_and_rejects_truncation():
    with patch("httpx.AsyncClient.post", AsyncMock(return_value=reply(json.dumps({"natural_text": "x"})))):
        assert await svc.extract_text_local(image_pdf(1)) == "x"
    with patch("httpx.AsyncClient.post", AsyncMock(return_value=reply("partial", done_reason="length"))):
        with pytest.raises(Exception, match="^OCR processing error"):
            await svc.extract_text_local(image_pdf(1))


async def test_local_ocr_error_is_wrapped():
    with patch("httpx.AsyncClient.post", AsyncMock(side_effect=httpx.ConnectError("refused"))):
        with pytest.raises(Exception, match="^OCR processing error"):
            await svc.extract_text_local(image_pdf(1))


async def test_provider_switch(monkeypatch):
    pdf = image_pdf(1)  # no text layer, so OCR is needed
    typhoon, local = AsyncMock(return_value="cloud"), AsyncMock(return_value="local")
    monkeypatch.setattr(svc, "extract_text_typhoon", typhoon)
    monkeypatch.setattr(svc, "extract_text_local", local)
    monkeypatch.delenv("OCR_PROVIDER", raising=False)
    assert (await svc.extract_document(pdf))[0] == "cloud"
    monkeypatch.setenv("OCR_PROVIDER", "ollama")
    assert (await svc.extract_document(pdf))[0] == "local"
