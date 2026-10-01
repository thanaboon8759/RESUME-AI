"""
Local LLM extraction engine using instructor + Ollama.

Uses the OpenAI-compatible API exposed by Ollama (http://localhost:11434/v1)
together with the ``instructor`` library to coerce local LLM output into
validated Pydantic models defined in ``schemas.models``.

Typical usage::

    from extraction.llm_local import extract_candidate_profile, extract_with_fallback

    profile = extract_candidate_profile(markdown_text)
    profile, model_used = extract_with_fallback(markdown_text)
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import urllib.request
import instructor
from openai import OpenAI

from schemas.models import CandidateProfile

logger = logging.getLogger(__name__)

# ── Ollama OpenAI-compatible client ─────────────────────────────────────

OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_API_KEY = "ollama"  # Ollama ignores the key but the client requires one

DEFAULT_MODELS: list[str] = [
    "qwen2.5:7b",
    "deepseek-r1:8b",
    "scb10x/typhoon2:8b",
    "gemma2:9b",
    "llama3.1:8b",
    "mistral:7b",
]

_SYSTEM_PROMPT = """\
You are an expert AI talent intelligence agent and resume parsing system.

Given the markdown text of a resume, extract all relevant fields and return them \
as a single JSON object conforming strictly to the CandidateProfile schema.

### Extraction rules
- **full_name**: The candidate's full name exactly as written.
- **contact_email**: The primary email address, or null if missing.
- **contact_phone**: The primary phone number, or null if missing.
- **languages**: Human spoken/written languages (e.g. ["Thai", "English"]).
- **skills**: Explicitly stated technical and soft skills (languages, frameworks, tools, security tools, databases, soft skills).
- **implicit_skills**: Skills clearly demonstrated in project achievements or profile description but not explicitly listed in skills section.
- **seniority_level**: Estimate candidate seniority level: "Junior" (<2 yrs or student/intern), "Mid-Level" (2-5 yrs), "Senior" (5-8 yrs), "Lead/Principal" (8+ yrs or team lead), or "Executive". For students, interns, or fresh graduates, always assign "Junior".
- **total_years_experience**: Floating-point calculation of total professional/internship years based on work dates (0.0 to 1.0 for students/interns).
- **executive_summary**: High-impact 2-3 sentence executive profile summarizing the candidate's core expertise, domain experience, and key value proposition.
- **extraction_confidence**: Self-assessed confidence score between 0.0 and 1.0 based on document clarity.
- **experience**: List of work-experience entries ordered most recent first. For students or recent graduates, also include substantive technical projects, CTF competitions, or internship roles listed in the experience section.
- **education**: List of degrees, institutions, and graduation years.

### Important
- Handle English, Thai, and bilingual Thai-English resumes seamlessly.
- Preserve Thai Buddhist Era dates (e.g., 2564) and institution names accurately.
- Return valid JSON adhering to the schema.
"""


def _build_client() -> instructor.Instructor:
    """Build an instructor-patched OpenAI client pointing at Ollama."""
    return instructor.from_openai(
        OpenAI(base_url=OLLAMA_BASE_URL, api_key=OLLAMA_API_KEY),
        mode=instructor.Mode.JSON,
    )


# ── Connectivity check ──────────────────────────────────────────────────


def check_ollama_connectivity(timeout: float = 5.0) -> bool:
    """Return True if the Ollama server is reachable.

    Sends a lightweight GET to ``http://localhost:11434/api/tags`` which
    lists available models without performing any inference.
    """
    try:
        resp = urllib.request.urlopen(
            "http://localhost:11434/api/tags",
            timeout=timeout,
        )
        import json as _json
        data = _json.loads(resp.read().decode())
        logger.debug("Ollama connectivity OK — %d models available", len(data.get("models", [])))
        return True
    except Exception as exc:
        logger.error("Ollama connectivity check failed: %s", exc)
        return False


class OllamaConnectionError(RuntimeError):
    """Raised when the Ollama server is not reachable."""


class ExtractionError(RuntimeError):
    """Raised when structured extraction fails for all attempted models."""


# ── Core extraction ─────────────────────────────────────────────────────


def extract_candidate_profile(
    markdown_text: str,
    model: str = "qwen2.5:7b",
) -> CandidateProfile:
    """Extract a :class:`CandidateProfile` from resume markdown text.

    Parameters
    ----------
    markdown_text:
        The full markdown text of a parsed resume.
    model:
        Ollama model tag to use for inference (default ``qwen2.5:7b``).

    Returns
    -------
    CandidateProfile
        Validated Pydantic model populated with extracted data.

    Raises
    ------
    OllamaConnectionError
        If the Ollama server is unreachable.
    ExtractionError
        If the LLM fails to produce a valid response after retries.
    """
    if not check_ollama_connectivity():
        raise OllamaConnectionError(
            f"Cannot reach Ollama at {OLLAMA_BASE_URL}. "
            "Is the Ollama server running?"
        )

    client = _build_client()

    logger.info("Starting extraction with model '%s' …", model)
    start = time.perf_counter()

    try:
        profile: CandidateProfile = client.chat.completions.create(
            model=model,
            response_model=CandidateProfile,
            max_retries=2,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": markdown_text},
            ],
        )
    except Exception as exc:
        elapsed = time.perf_counter() - start
        logger.error(
            "Extraction failed with model '%s' after %.2fs: %s",
            model,
            elapsed,
            exc,
        )
        raise ExtractionError(
            f"Model '{model}' failed to extract a valid CandidateProfile: {exc}"
        ) from exc

    elapsed = time.perf_counter() - start
    logger.info(
        "Extraction succeeded with model '%s' in %.2fs — name='%s', "
        "%d skills, %d experience entries, %d education entries",
        model,
        elapsed,
        profile.full_name,
        len(profile.skills),
        len(profile.experience),
        len(profile.education),
    )
    return profile


# ── Multi-model fallback ────────────────────────────────────────────────


def extract_with_fallback(
    markdown_text: str,
    models: Optional[list[str]] = None,
) -> tuple[CandidateProfile, str]:
    """Try multiple models in sequence, returning the first successful result.

    Parameters
    ----------
    markdown_text:
        The full markdown text of a parsed resume.
    models:
        Ordered list of Ollama model tags to attempt.  Defaults to
        ``['qwen2.5:7b', 'llama3.1:8b', 'mistral:7b']``.

    Returns
    -------
    tuple[CandidateProfile, str]
        ``(profile, model_used)`` — the extracted profile and the tag of the
        model that produced it.

    Raises
    ------
    OllamaConnectionError
        If the Ollama server is unreachable before any attempt.
    ExtractionError
        If **all** models in the list fail.
    """
    if models is None:
        models = list(DEFAULT_MODELS)

    if not models:
        raise ValueError("At least one model must be provided.")

    # Single connectivity check up front to fail fast.
    if not check_ollama_connectivity():
        raise OllamaConnectionError(
            f"Cannot reach Ollama at {OLLAMA_BASE_URL}. "
            "Is the Ollama server running?"
        )

    errors: list[tuple[str, Exception]] = []

    for model in models:
        try:
            profile = extract_candidate_profile(markdown_text, model=model)
            return profile, model
        except ExtractionError as exc:
            logger.warning("Model '%s' failed, trying next … (%s)", model, exc)
            errors.append((model, exc))
        except OllamaConnectionError:
            # Server went away mid-sequence — no point trying more models.
            raise

    # All models exhausted.
    summary = "; ".join(f"{m}: {e}" for m, e in errors)
    raise ExtractionError(
        f"All models failed to extract a valid CandidateProfile. Errors: {summary}"
    )


# ── CLI convenience ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    sample = """\
# John Doe

**Email:** john.doe@example.com  
**Phone:** +66 81 234 5678

## Skills
Python, FastAPI, Docker, PostgreSQL, Machine Learning, Thai, English

## Experience

### Senior Software Engineer — Acme Corp
*Jan 2022 – Present*
- Led migration of monolith to microservices
- Reduced API latency by 40%

### Software Engineer — Widgets Inc.
*Mar 2019 – Dec 2021*
- Built internal tooling with Python and React
- Mentored 3 junior developers

## Education

### Chulalongkorn University
B.Eng. Computer Engineering, 2018
"""

    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as fh:
            sample = fh.read()

    try:
        profile, used = extract_with_fallback(sample)
        print(f"\n✅ Extracted with model: {used}")
        print(profile.model_dump_json(indent=2))
    except (OllamaConnectionError, ExtractionError) as err:
        print(f"\n❌ {err}", file=sys.stderr)
        sys.exit(1)
