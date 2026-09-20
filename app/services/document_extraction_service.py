import os
import json
import httpx
import logging
from io import BytesIO
import fitz

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

# Environment variables
TYPHOON_API_KEY = os.getenv("TYPHOON_API_KEY")
TYPHOON_MODEL_NAME = os.getenv("TYPHOON_MODEL_NAME", "typhoon-ocr")

def extract_text_fitz(file_bytes: bytes) -> tuple[str, list[dict]]:
    """Extract text and bounding blocks using PyMuPDF (fitz)."""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        blocks = []
        block_id = 0
        for page_num, page in enumerate(doc):
            rect = page.rect
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                if "lines" in block:
                    block_text = ""
                    for line in block["lines"]:
                        for span in line["spans"]:
                            block_text += span["text"] + " "
                        block_text += "\n"
                    block_text = block_text.strip()
                    if block_text:
                        text += f"[ID: b{block_id}] {block_text}\n\n"
                        x0, y0, x1, y1 = block["bbox"]
                        blocks.append({
                            "id": f"b{block_id}",
                            "text": block_text,
                            "bbox": {
                                "x": x0 / rect.width if rect.width else 0,
                                "y": y0 / rect.height if rect.height else 0,
                                "width": (x1 - x0) / rect.width if rect.width else 0,
                                "height": (y1 - y0) / rect.height if rect.height else 0
                            },
                            "page": page_num + 1
                        })
                        block_id += 1
        return text.strip(), blocks
    except Exception as e:
        logger.error(f"fitz extraction error: {e}")
        return "", []

def is_extraction_usable(text: str) -> bool:
    """Validate if PyMuPDF extracted text is usable or just garbled font encoding."""
    import re
    # Remove block IDs for analysis
    clean_text = re.sub(r'\[ID: b\d+\]', '', text)
    
    # 1. Meaningful character count
    meaningful_chars = len(clean_text.replace(" ", "").replace("\n", ""))
    if meaningful_chars < 100:
        return False
        
    # 2. Ratio of replacement characters
    replacement_chars = clean_text.count('\ufffd') + clean_text.count("?")
    if replacement_chars / max(1, meaningful_chars) > 0.1: # >10% corrupted
        return False
        
    # 3. Alphabetic/Thai/English vs Symbol ratio
    # Matches English letters, Thai letters/numbers, digits
    alphanumeric_count = len(re.findall(r'[a-zA-Z0-9ก-๛]', clean_text))
    # If < 40% of the meaningful characters are actual letters/numbers, it's likely wingdings or garbled
    if alphanumeric_count / max(1, meaningful_chars) < 0.4:
        return False
        
    # 4. Excessive repeated characters (e.g. "       ", ".....")
    # This might happen in valid resumes, but usually alphabetic ratio protects against it.
    
    return True

async def extract_text_typhoon(file_bytes: bytes) -> str:
    """Fallback OCR extraction using Typhoon."""
    if not TYPHOON_API_KEY or TYPHOON_API_KEY == "mock":
        return "Mock Typhoon OCR text extracted from image-based PDF. Candidate has 5 years of Python experience and loves building APIs with FastAPI."
    
    url = "https://api.opentyphoon.ai/v1/ocr"
    
    async with httpx.AsyncClient() as client:
        files = {"file": ("document.pdf", file_bytes, "application/pdf")}
        data = {
            'model': TYPHOON_MODEL_NAME,
            'task_type': 'default',
            'max_tokens': '16384',
            'temperature': '0.1',
            'top_p': '0.6',
            'repetition_penalty': '1.2'
        }
        headers = {"Authorization": f"Bearer {TYPHOON_API_KEY}"}
        try:
            response = await client.post(url, files=files, data=data, headers=headers, timeout=60.0)
            response.raise_for_status()
            result = response.json()
            
            extracted_texts = []
            for page_result in result.get('results', []):
                if page_result.get('success') and page_result.get('message'):
                    content = page_result['message']['choices'][0]['message']['content']
                    try:
                        parsed_content = json.loads(content)
                        text = parsed_content.get('natural_text', content)
                    except json.JSONDecodeError:
                        text = content
                    extracted_texts.append(text)
                elif not page_result.get('success'):
                    logger.error(f"Typhoon OCR error processing page: {page_result.get('error', 'Unknown error')}")

            return '\n'.join(extracted_texts) if extracted_texts else ""
        except Exception as e:
            logger.error(f"Typhoon OCR error: {e}")
            raise Exception(f"OCR processing error: {e}")

async def extract_document(file_bytes: bytes) -> tuple[str, list[dict]]:
    """
    Core document extraction flow:
    1. Try fitz (PyMuPDF)
    2. Check sufficiency
    3. Fallback to Typhoon OCR if needed
    Returns: (extracted_text, blocks)
    """
    logger.info("Document extraction started")
    text, blocks = extract_text_fitz(file_bytes)
    
    if not is_extraction_usable(text):
        logger.info(f"fitz text insufficient or corrupted, falling back to Typhoon OCR...")
        text = await extract_text_typhoon(file_bytes)
        blocks = [] # OCR currently does not return bboxes
        logger.info("Typhoon OCR completed")
    else:
        logger.info("fitz text sufficient: true")
        
    return text, blocks
