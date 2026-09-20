import os
import json
import logging
from openai import AsyncOpenAI
from pydantic import ValidationError
from app.schemas.candidate import CandidateProfile

logger = logging.getLogger(__name__)

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
QWEN_API_URL = os.getenv("QWEN_API_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL_NAME = os.getenv("QWEN_MODEL_NAME", "qwen3.8-flash")

qwen_client = AsyncOpenAI(
    api_key=DASHSCOPE_API_KEY or "mock",
    base_url=QWEN_API_URL,
    timeout=300.0,
    max_retries=2
)

async def analyze_resume_facts_with_qwen(text: str, candidate_name: str) -> CandidateProfile:
    """Analyze the extracted text using Qwen to extract factual information only."""
    if not DASHSCOPE_API_KEY or DASHSCOPE_API_KEY == "mock":
        return CandidateProfile(
            personal_info={"name": candidate_name, "email": "mock@test.com", "phone": "12345", "location": "Bangkok", "website": None, "github": None, "linkedin": None},
            education=[{"institution": "Mock University", "degree": "BS CS", "dates": "2018-2022"}],
            experience=[{"company": "Mock Corp", "position": "Developer", "dates": "2022-2024", "responsibilities": ["Coding"]}],
            projects=[{"title": "Mock Project", "description": "A project", "technologies": ["Python"]}],
            skills=[{"name": "Python", "evidence": {"quote": "Python", "block_ids": []}}, {"name": "FastAPI", "evidence": {"quote": "FastAPI", "block_ids": []}}],
            certifications=[],
            languages=["English"]
        )

    system_prompt = (
        "You are an AI system responsible for extracting strictly factual information from resumes. "
        "Your task is to analyze the provided resume text and map the information into a predefined JSON structure.\n\n"
        "Rules:\n"
        "1. Extract ONLY factual information explicitly present in the resume.\n"
        "2. DO NOT perform candidate screening, scoring, or decision making.\n"
        "3. DO NOT invent, guess, or hallucinate missing information.\n"
        "4. Return null for missing single-value fields (e.g., if there is no email, return null).\n"
        "5. Return an empty array for missing list fields.\n"
        "6. IMPORTANT - Contact Info: Extract actual emails, phone numbers, GitHub/LinkedIn links, and addresses. "
        "DO NOT treat labeled fields (e.g. 'Email:', 'Phone:') as placeholders. If it says 'Email: [someone@example.com]', "
        "extract 'someone@example.com'. If it literally says 'Email...', it is a placeholder, return null.\n"
        "7. IMPORTANT - Location: Extract specific locations (city/province) only when supported by the text. Do not guess.\n"
        "8. Correctly associate related information. Use headings, surrounding text, and dates to determine relationships "
        "(e.g., company -> position -> dates, institution -> degree -> dates, project -> title -> description).\n"
        "9. Do NOT assume that sequential block order represents semantic reading order. Ignore fragmented IDs.\n"
        "10. Preserve Thai, English, and mixed content in its original language without unnecessary translation.\n"
        "11. Evidence: For every important extracted field (e.g. university name, company name, project, skill), "
        "attach an `evidence` object with the exact quote into the `evidence` field. Include `block_ids` if present (e.g., '[\"b0\"]'). "
        "If no block IDs are present, leave `block_ids` empty.\n"
        "12. Return valid JSON only, matching the exact following schema structure:\n"
        '{\n'
        '  "personal_info": {"name": "...", "email": "...", "phone": "...", "location": "...", "website": "...", "github": "...", "linkedin": "..."},\n'
        '  "education": [{"institution": "...", "degree": "...", "dates": "...", "evidence": {"quote": "...", "block_ids": ["b1"]}}],\n'
        '  "experience": [{"company": "...", "position": "...", "dates": "...", "responsibilities": ["..."], "evidence": {"quote": "...", "block_ids": ["b2"]}}],\n'
        '  "projects": [{"title": "...", "description": "...", "technologies": ["..."], "evidence": {"quote": "...", "block_ids": ["b3"]}}],\n'
        '  "skills": [{"name": "...", "evidence": {"quote": "...", "block_ids": ["b4"]}}],\n'
        '  "certifications": [{"name": "...", "issuer": "...", "date": "...", "evidence": {"quote": "...", "block_ids": []}}],\n'
        '  "languages": ["...", "..."]\n'
        '}'
    )

    try:
        logger.info("Qwen #1 (Resume Extraction) started")
        response = await qwen_client.chat.completions.create(
            model=QWEN_MODEL_NAME, 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Candidate Name: {candidate_name}\n\nResume Text:\n{text}"}
            ],
            response_format={"type": "json_object"},
            extra_body={"enable_thinking": True}
        )
        
        result_text = response.choices[0].message.content
        data = json.loads(result_text)
        logger.info("Qwen #1 (Resume Extraction) completed")
        return CandidateProfile(**data)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid Qwen JSON: {e}")
        raise Exception(f"AI processing error (invalid JSON): {e}")
    except ValidationError as e:
        logger.error(f"Validation error for Qwen response: {e}")
        raise Exception(f"AI processing error (schema validation): {e}")
    except Exception as e:
        logger.error(f"Qwen API error: {e}")
        raise Exception(f"AI processing error: {e}")
