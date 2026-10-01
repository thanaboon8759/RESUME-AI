import os
import json
import logging
from openai import AsyncOpenAI
from pydantic import ValidationError
from app.schemas.candidate import CandidateProfile, ScreeningResult
from app.schemas.job import Job

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

async def screen_candidate_with_qwen(profile: CandidateProfile, job: Job) -> ScreeningResult:
    """Analyze the extracted candidate profile against job requirements using Qwen #2."""
    if not DASHSCOPE_API_KEY or DASHSCOPE_API_KEY == "mock":
        from app.schemas.core import DecisionEnum
        return ScreeningResult(
            score=85,
            decision=DecisionEnum.shortlisted,
            role=job.title,
            headline="Mock AI Headline",
            experience_summary="Matched based on profile",
            location="Mock Location",
            strengths=["Matched skill A"],
            weaknesses=["Missing skill B"],
            missingInformation=[],
            detectedLanguages=["English"],
            reasons=["Strong candidate"],
            criteria=[]
        )

    system_prompt = (
        "You are an AI Screening system. Your task is to compare a structured 'Candidate Profile' "
        "against 'Job Requirements' and produce a final screening result.\n\n"
        "Rules:\n"
        "1. Screen ONLY based on the provided Candidate Profile data and the Job Requirements.\n"
        "2. Do not invent, guess, or hallucinate missing information.\n"
        "3. Evaluate Required criteria, Preferred criteria, and Mandatory criteria as defined in the Job Requirements.\n"
        "4. Calculate a score (1-100) based on how well the candidate matches the job.\n"
        "5. Output a decision: 'shortlisted' or 'rejected'.\n"
        "6. Provide reasons, strengths, weaknesses, and a list of evaluated criteria.\n"
        "7. EVIDENCE: You MUST NOT invent or generate evidence quotes yourself. Instead, you must return an `evidence_refs` array pointing to the exact field and value in the CandidateProfile that supports the criterion. The `field` MUST be a top-level key (e.g., 'skills', 'experience', 'projects', 'education') and must NOT use dot or bracket notation.\n"
        "8. Do not make decisions based on arbitrary assumptions; strictly match the profile facts to the job needs.\n"
        "9. Return valid JSON only, matching the exact following schema structure:\n"
        '{\n'
        '  "score": 1-100,\n'
        '  "decision": "shortlisted" | "rejected",\n'
        '  "role": "...",\n'
        '  "headline": "...",\n'
        '  "experience_summary": "...",\n'
        '  "location": "...",\n'
        '  "strengths": ["...", "..."],\n'
        '  "weaknesses": ["...", "..."],\n'
        '  "missingInformation": ["...", "..."],\n'
        '  "detectedLanguages": ["...", "..."],\n'
        '  "reasons": ["...", "..."],\n'
        '  "criteria": [{"label": "...", "status": "met" | "unmet" | "partial", "evidence_refs": [{"field": "skills", "value": "Python"}]}]\n'
        '}'
    )

    try:
        logger.info("Qwen #2 (Screening) started")
        response = await qwen_client.chat.completions.create(
            model=QWEN_MODEL_NAME, 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Candidate Profile:\n{profile.model_dump_json(indent=2)}\n\nJob Requirements:\n{job.model_dump_json(indent=2)}"}
            ],
            response_format={"type": "json_object"},
            extra_body={"enable_thinking": True}
        )
        
        result_text = response.choices[0].message.content
        data = json.loads(result_text)
        logger.info("Qwen #2 (Screening) completed")
        return ScreeningResult(**data)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid Qwen JSON: {e}")
        raise Exception(f"AI screening error (invalid JSON): {e}")
    except ValidationError as e:
        logger.error(f"Validation error for Qwen response: {e}")
        raise Exception(f"AI screening error (schema validation): {e}")
    except Exception as e:
        logger.error(f"Qwen API error: {e}")
        raise Exception(f"AI screening error: {e}")
