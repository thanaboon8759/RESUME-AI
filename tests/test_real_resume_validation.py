"""
Real-Resume Validation Test — Jakapan Ploensup

Validates the complete pipeline with real resume data:
  PyMuPDF blocks → Qwen #1 → CandidateProfile + FactEvidence
  → Qwen #2 → ScreeningResult + evidence_refs → Backend evidence resolution

This test does NOT mock AI responses.
All assertions are against the live Qwen API.

Architecture: we call Qwen #1 once and cache the result in a module-level
dictionary so all test functions share the same profile object without
async fixture scoping issues.
"""
import os
import re
import json
import pytest
import asyncio
from dotenv import load_dotenv
load_dotenv()
LIVE = os.getenv("DASHSCOPE_API_KEY") not in (None, "", "mock")  # without a key the services return fake data

from app.services.resume_extraction_service import analyze_resume_facts_with_qwen
from app.services.screening_service import screen_candidate_with_qwen
from app.schemas.job import Job
from app.schemas.core import DecisionEnum, CriterionStatusEnum
from app.services.scoring import apply_job_rules


# ---------------------------------------------------------------------------
# Evidence helpers
# ---------------------------------------------------------------------------

def normalize_evidence_text(text: str) -> str:
    """Collapse whitespace only. Preserve all other characters."""
    return re.sub(r"\s+", " ", text).strip()


def evidence_exists(quote: str, source_text: str) -> bool:
    return normalize_evidence_text(quote) in normalize_evidence_text(source_text)


def strip_block_markers(text: str) -> str:
    """Remove [ID: bX] PyMuPDF block markers so evidence quotes that span
    multiple blocks (e.g. b5+b6 concatenated) can still be validated."""
    return re.sub(r"\[ID:\s*b\d+\]\s*", "", text)


# ---------------------------------------------------------------------------
# Real resume text (PyMuPDF block order as extracted)
# ---------------------------------------------------------------------------

REAL_RESUME = """\
[ID: b0] EDUCATION

[ID: b1] Motivated computer science student with \
hands-on experience in web \
development, automation, and basic AI- \
based systems through academic \
projects and self-learning. Skilled in \
building functional web applications, \
integrating APIs, and solving technical \
problems. Fast learner with strong \
adaptability to new technologies and a \
commitment to delivering solutions that \
meet project requirements.

[ID: b2] PROFILE SUMMARY

[ID: b3] Jakapan Ploensup

[ID: b4] EXPERIENCE

[ID: b5] Freelance Web Developer ( 2024 - Present)

[ID: b6] Partnered directly with clients to analyze technical requirements, plan \
development sprints, and deliver custom web applications on time. \
Developed and deployed full-stack web platforms using Next.js, \
integrating modern backend architectures and databases such as \
Firebase, MongoDB, and Supabase. \
Managed media storage and optimization using Cloudinary, \
significantly improving page load speeds and overall performance. \
Designed and maintained automation scripts and AI-based solutions, \
troubleshooting bugs and providing ongoing post-deployment support.

[ID: b7] SELECTED TECHNICAL PROJECTS

[ID: b8] AI Product Moderation System (Senior Project)

[ID: b9] Developed an exclusive full-stack e-commerce platform tailored for \
Bangkok University students using Next.js and MongoDB, featuring an \
automated moderation system to detect and block illegal product \
listings before publication. \
Engineered a custom AI-driven backend using Python to analyze \
product data, integrating Cloudinary for scalable image storage and \
efficient visual evaluation

[ID: b10] Game Boss Automation Bot

[ID: b11] Programmed a specialized automation bot using Python and ADB \
(Android Debug Bridge) to autonomously execute complex, repetitive \
in-game tasks. \
Integrated OpenCV to implement computer vision capabilities, allowing \
the bot to accurately recognize on-screen elements and adapt to \
dynamic gameplay.

[ID: b12] AI Music Recommendation Engine

[ID: b13] Developed a predictive machine learning model using Python to \
analyze audio data and user listening patterns. \
Designed and trained Neural Networks to accurately classify genres \
and generate highly personalized music recommendations.

[ID: b14] Personal Portfolio Website

[ID: b15] Designed and developed a responsive, high-performance portfolio \
utilizing Next.js to showcase technical projects, code repositories, \
and AWS/Cybersecurity certifications.

[ID: b16] Faculty : School of Information and \
Technology Innovation \
Computer Science Data Science and Cyber Security \
Bangkok University \
July 2023 - Present

[ID: b17] Email:nongkhun2015@gmail.com \
Github:https://github.com/JKP456 \
LikedIn:www.linkedin.com/in/jakapan \
MyWebsite: jkp456.github.io/portfolio

[ID: b18] 9, 16th Floor, 17 Phahonyothin \
Road, \
Khlong Nueng, Khlong Luang, \
Pathum Thani, Thailand \
092-8835189

[ID: b19] CONTACT

[ID: b20] SKILLS

[ID: b21] Programming Languages: Python, JavaScript, HTML, CSS \
Web Frameworks & APIs: Next.js, Stripe API \
Databases & Backend as a Service (BaaS): Firebase, \
MongoDB, Supabase, Prisma \
Cloud & Infrastructure: AWS (EC2), Cloudinary \
AI, Machine Learning & Automation: Neural Networks, \
Computer Vision (OpenCV), Automation (ADB) \
Core Computer Science & Security: Cybersecurity \
principles, Algorithm Design (Dynamic Programming, \
Greedy Algorithms, Divide & Conquer)

[ID: b22] English Program \
Sawananan Wittaya School

[ID: b23] 2019 - 2023
"""

# Marker-stripped version used to validate Qwen #1 evidence quotes.
# Qwen correctly merges adjacent blocks and strips [ID: bX] markers,
# so we must check against the clean content rather than the raw extraction.
REAL_RESUME_STRIPPED = strip_block_markers(REAL_RESUME)

EXPECTED_SKILLS = {
    "python", "javascript", "html", "css", "next.js", "firebase",
    "mongodb", "supabase", "cloudinary", "aws", "neural networks",
    "opencv", "adb",
}

FORBIDDEN_SKILLS = {
    "react", "docker", "kubernetes", "pytorch", "tensorflow",
    "postgresql", "fastapi", "django", "flask", "redis",
}

PROJECT_KEYWORDS = [
    "ai product moderation",
    "game boss automation",
    "ai music recommendation",
    "personal portfolio",
]

NEGATIVE_EVIDENCE = [
    "Skills: Python",
    "Python and Django",
    "Experienced React Developer",
    "5 years of professional experience",
    "Bachelor's degree completed",
    "Expert in PostgreSQL",
]

# ---------------------------------------------------------------------------
# Job definitions
# ---------------------------------------------------------------------------

JOB_A = Job(
    id="real-job-a", title="Full-Stack Developer", jd="Full-Stack Developer role",
    required=["Python", "Next.js", "Full-stack web development experience",
               "Computer Science education", "At least 1 year web development experience"],
    preferred=["AWS", "MongoDB", "Supabase", "AI/ML experience"],
    weights={}, experience="1+", education="BS", location="", salary="", mandatory=["Python", "Next.js"],
)
JOB_B = Job(
    id="real-job-b", title="Backend Developer", jd="Backend Developer",
    required=["Python", "Next.js", "React", "PostgreSQL"],
    preferred=[],
    weights={}, experience="", education="", location="", salary="", mandatory=["React", "PostgreSQL"],
)
JOB_C = Job(
    id="real-job-c", title="Senior Web Developer", jd="Senior Web Developer",
    required=["At least 2 years of professional web development experience"],
    preferred=["Next.js", "Python"],
    weights={}, experience="2+", education="", location="", salary="", mandatory=[],
)
JOB_D = Job(
    id="real-job-d", title="AI/ML Engineer", jd="AI/ML Engineer",
    required=["Python", "Machine Learning", "Neural Networks", "Computer Vision"],
    preferred=["OpenCV", "ADB"],
    weights={}, experience="", education="", location="", salary="", mandatory=["Python", "Machine Learning"],
)
JOB_E = Job(
    id="real-job-e", title="CS Graduate", jd="Graduate role",
    required=["Bachelor's degree in Computer Science"],
    preferred=[],
    weights={}, experience="", education="BS", location="", salary="", mandatory=[],
)

# ---------------------------------------------------------------------------
# Module-level cache: call Qwen #1 exactly once
# ---------------------------------------------------------------------------

_CACHE: dict = {}


async def get_profile():
    if not LIVE:
        pytest.skip("needs DASHSCOPE_API_KEY")
    if "profile" not in _CACHE:
        _CACHE["profile"] = await analyze_resume_facts_with_qwen(REAL_RESUME, "Jakapan Ploensup")
    return _CACHE["profile"]


async def get_result(job_key: str, job: Job):
    if job_key not in _CACHE:
        profile = await get_profile()
        # Assert on the decision HR sees: the job rules replace Qwen's own score/decision.
        _CACHE[job_key] = apply_job_rules(await screen_candidate_with_qwen(profile, job), job)[0]
    return _CACHE[job_key]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def skill_names(profile) -> set:
    return {s.name.lower() for s in profile.skills}


def find_criterion(result, label: str):
    label_lower = label.lower()
    for c in result.criteria:
        if label_lower in c.label.lower() or c.label.lower() in label_lower:
            return c
    return None


# ===========================================================================
# Negative evidence — pure unit tests, no network needed
# ===========================================================================

@pytest.mark.parametrize("fake_quote", NEGATIVE_EVIDENCE)
def test_fabricated_evidence_rejected(fake_quote):
    assert not evidence_exists(fake_quote, REAL_RESUME), (
        f"Fabricated evidence incorrectly passed: '{fake_quote}'"
    )


# ===========================================================================
# Qwen #1 — CandidateProfile validation
# ===========================================================================

@pytest.mark.asyncio
async def test_q1_returns_profile():
    from app.schemas.candidate import CandidateProfile
    profile = await get_profile()
    assert isinstance(profile, CandidateProfile)


@pytest.mark.asyncio
async def test_q1_no_score_or_decision():
    profile = await get_profile()
    assert not hasattr(profile, "score")
    assert not hasattr(profile, "decision")


@pytest.mark.asyncio
async def test_q1_name_extracted():
    profile = await get_profile()
    assert profile.personal_info.name is not None
    assert "jakapan" in profile.personal_info.name.lower(), (
        f"Expected 'Jakapan' in name, got: {profile.personal_info.name}"
    )


@pytest.mark.asyncio
async def test_q1_email_extracted():
    profile = await get_profile()
    assert profile.personal_info.email is not None
    assert "nongkhun2015@gmail.com" in profile.personal_info.email.lower(), (
        f"Email not correctly extracted: {profile.personal_info.email}"
    )


@pytest.mark.asyncio
async def test_q1_github_extracted():
    profile = await get_profile()
    github = profile.personal_info.github or ""
    assert "github.com/jkp456" in github.lower(), (
        f"GitHub not correctly extracted: {github}"
    )


@pytest.mark.asyncio
async def test_q1_freelance_experience_present():
    profile = await get_profile()
    assert len(profile.experience) >= 1, "Expected at least 1 experience entry"
    combined = " ".join(
        str(e.get("company", "")) + " " + str(e.get("position", "")) + " " + str(e.get("title", ""))
        for e in profile.experience
    ).lower()
    assert "freelance" in combined or "web developer" in combined, (
        f"'Freelance Web Developer' not found in experience: {profile.experience}"
    )


@pytest.mark.asyncio
async def test_q1_projects_not_in_experience():
    """Academic projects must NOT appear as employment."""
    profile = await get_profile()
    experience_text = json.dumps(profile.experience).lower()
    for kw in PROJECT_KEYWORDS:
        assert kw not in experience_text, (
            f"Project '{kw}' incorrectly placed inside experience!"
        )


@pytest.mark.asyncio
async def test_q1_four_projects_extracted():
    profile = await get_profile()
    assert len(profile.projects) >= 4, (
        f"Expected ≥4 projects, got {len(profile.projects)}: "
        f"{[p.get('title') for p in profile.projects]}"
    )


@pytest.mark.asyncio
async def test_q1_ai_moderation_project():
    profile = await get_profile()
    titles = [p.get("title", "").lower() for p in profile.projects]
    assert any("moderation" in t or "ai product" in t for t in titles), (
        f"'AI Product Moderation System' not in projects: {titles}"
    )


@pytest.mark.asyncio
async def test_q1_game_bot_project():
    profile = await get_profile()
    titles = [p.get("title", "").lower() for p in profile.projects]
    assert any("game" in t or "bot" in t or "automation" in t for t in titles), (
        f"'Game Boss Automation Bot' not in projects: {titles}"
    )


@pytest.mark.asyncio
async def test_q1_music_recommendation_project():
    profile = await get_profile()
    titles = [p.get("title", "").lower() for p in profile.projects]
    assert any("music" in t or "recommendation" in t for t in titles), (
        f"'AI Music Recommendation Engine' not in projects: {titles}"
    )


@pytest.mark.asyncio
async def test_q1_portfolio_project():
    profile = await get_profile()
    titles = [p.get("title", "").lower() for p in profile.projects]
    assert any("portfolio" in t for t in titles), (
        f"'Personal Portfolio Website' not in projects: {titles}"
    )


@pytest.mark.asyncio
async def test_q1_two_education_records():
    profile = await get_profile()
    assert len(profile.education) >= 2, (
        f"Expected Bangkok University + high school, got: {profile.education}"
    )


@pytest.mark.asyncio
async def test_q1_bangkok_university():
    profile = await get_profile()
    institutions = [e.get("institution", "").lower() for e in profile.education]
    assert any("bangkok" in i for i in institutions), (
        f"Bangkok University not found: {institutions}"
    )


@pytest.mark.asyncio
async def test_q1_high_school():
    profile = await get_profile()
    institutions = [e.get("institution", "").lower() for e in profile.education]
    assert any("sawananan" in i or "wittaya" in i for i in institutions), (
        f"Sawananan Wittaya not found: {institutions}"
    )


@pytest.mark.asyncio
async def test_q1_university_ongoing():
    """Must not claim graduation — source says 'Present'."""
    profile = await get_profile()
    for edu in profile.education:
        if "bangkok" in edu.get("institution", "").lower():
            dates = edu.get("dates", "").lower()
            assert any(kw in dates for kw in ["present", "ongoing", "current", "2023"]), (
                f"Bangkok University dates should show ongoing, got: '{dates}'"
            )


@pytest.mark.asyncio
async def test_q1_expected_skills_present():
    profile = await get_profile()
    names = skill_names(profile)
    missing = [s for s in EXPECTED_SKILLS if not any(s in n or n in s for n in names)]
    assert not missing, (
        f"Expected skills missing: {missing}\nExtracted: {sorted(names)}"
    )


@pytest.mark.asyncio
async def test_q1_forbidden_skills_absent():
    profile = await get_profile()
    names = skill_names(profile)
    hallucinated = [s for s in FORBIDDEN_SKILLS if s in names]
    assert not hallucinated, (
        f"Hallucinated (not in resume) skills: {hallucinated}"
    )


@pytest.mark.asyncio
async def test_q1_skill_evidence_quotes_real():
    profile = await get_profile()
    hallucinated = [
        (s.name, s.evidence.quote)
        for s in profile.skills
        if s.evidence and s.evidence.quote and not evidence_exists(s.evidence.quote, REAL_RESUME)
    ]
    assert not hallucinated, (
        "Hallucinated skill evidence (not in resume after whitespace normalisation):\n"
        + "\n".join(f"  [{n}] '{q}'" for n, q in hallucinated)
    )


@pytest.mark.asyncio
async def test_q1_experience_evidence_quotes_real():
    profile = await get_profile()
    # Qwen #1 correctly strips [ID: bX] markers and joins adjacent blocks.
    # We must validate against the marker-stripped resume, not the raw block text.
    hallucinated = [
        ev.get("quote", "")
        for exp in profile.experience
        for ev in [exp.get("evidence") or {}]
        if ev.get("quote") and not evidence_exists(ev["quote"], REAL_RESUME_STRIPPED)
    ]
    assert not hallucinated, (
        "Hallucinated experience evidence (not in marker-stripped resume):\n"
        + "\n".join(f"  '{q}'" for q in hallucinated)
    )


@pytest.mark.asyncio
async def test_q1_project_evidence_quotes_real():
    profile = await get_profile()
    # Qwen #1 concatenates project title block + description block, stripping markers.
    hallucinated = [
        (proj.get("title"), ev.get("quote", ""))
        for proj in profile.projects
        for ev in [proj.get("evidence") or {}]
        if ev.get("quote") and not evidence_exists(ev["quote"], REAL_RESUME_STRIPPED)
    ]
    assert not hallucinated, (
        "Hallucinated project evidence (not in marker-stripped resume):\n"
        + "\n".join(f"  [{t}] '{q}'" for t, q in hallucinated)
    )


@pytest.mark.asyncio
async def test_q1_education_evidence_quotes_real():
    profile = await get_profile()
    # Education evidence may span multiple adjacent blocks (e.g. b22 + b23).
    hallucinated = [
        (edu.get("institution"), ev.get("quote", ""))
        for edu in profile.education
        for ev in [edu.get("evidence") or {}]
        if ev.get("quote") and not evidence_exists(ev["quote"], REAL_RESUME_STRIPPED)
    ]
    assert not hallucinated, (
        "Hallucinated education evidence (not in marker-stripped resume):\n"
        + "\n".join(f"  [{i}] '{q}'" for i, q in hallucinated)
    )


# ===========================================================================
# Qwen #2 Screening — Case A: Strong Full-Stack Match
# ===========================================================================

@pytest.mark.asyncio
async def test_case_a_shortlisted():
    result = await get_result("a", JOB_A)
    assert result.decision == DecisionEnum.shortlisted, (
        f"Case A: Expected shortlisted, got {result.decision}. Score={result.score}. Reasons: {result.reasons}"
    )


@pytest.mark.asyncio
async def test_case_a_score_gte_70():
    result = await get_result("a", JOB_A)
    assert result.score >= 70, f"Case A: Expected score ≥ 70, got {result.score}"


@pytest.mark.asyncio
async def test_case_a_python_met_with_evidence_refs():
    result = await get_result("a", JOB_A)
    c = find_criterion(result, "Python")
    assert c is not None, f"Case A: Python not evaluated. Criteria: {[c.label for c in result.criteria]}"
    assert c.status == CriterionStatusEnum.met, f"Case A: Python should be met, got {c.status}"
    assert len(c.evidence_refs) > 0, "Case A: Python criterion must have evidence_refs"


@pytest.mark.asyncio
async def test_case_a_nextjs_met():
    result = await get_result("a", JOB_A)
    c = find_criterion(result, "Next.js")
    assert c is not None, f"Case A: Next.js not evaluated."
    assert c.status == CriterionStatusEnum.met, f"Case A: Next.js should be met, got {c.status}"


@pytest.mark.asyncio
async def test_case_a_no_synthesized_evidence():
    result = await get_result("a", JOB_A)
    for c in result.criteria:
        for ref in c.evidence_refs:
            assert "Skills:" not in ref.value, f"Case A: Synthesized 'Skills:' in ref: {ref}"
            assert "Experience:" not in ref.value, f"Case A: Synthesized 'Experience:' in ref: {ref}"
            assert "Education:" not in ref.value, f"Case A: Synthesized 'Education:' in ref: {ref}"


# ===========================================================================
# Case B: Missing React + PostgreSQL
# ===========================================================================

@pytest.mark.asyncio
async def test_case_b_rejected_or_low_score():
    result = await get_result("b", JOB_B)
    assert result.decision == DecisionEnum.rejected or result.score < 70, (
        f"Case B: Expected rejection or score < 70 (React+PostgreSQL absent). "
        f"Got decision={result.decision} score={result.score}"
    )


@pytest.mark.asyncio
async def test_case_b_react_not_met():
    result = await get_result("b", JOB_B)
    c = find_criterion(result, "React")
    if c is not None:
        assert c.status != CriterionStatusEnum.met, (
            f"Case B: React must NOT be 'met' (not in resume). Got: {c.status}"
        )


@pytest.mark.asyncio
async def test_case_b_postgresql_not_met():
    result = await get_result("b", JOB_B)
    c = find_criterion(result, "PostgreSQL")
    if c is not None:
        assert c.status != CriterionStatusEnum.met, (
            f"Case B: PostgreSQL must NOT be 'met' (not in resume). Got: {c.status}"
        )


# ===========================================================================
# Case C: 2+ years professional experience
# ===========================================================================

@pytest.mark.asyncio
async def test_case_c_experience_requirement_not_fully_met():
    """Freelance from 2024 is < 2 years. Projects must not count."""
    result = await get_result("c", JOB_C)
    c = find_criterion(result, "2 years")
    if c is not None:
        assert c.status != CriterionStatusEnum.met, (
            f"Case C: '2 years professional' should NOT be fully met (only freelance since 2024). "
            f"Got: {c.status}"
        )


# ===========================================================================
# Case D: AI/ML Engineer
# ===========================================================================

@pytest.mark.asyncio
async def test_case_d_shortlisted():
    result = await get_result("d", JOB_D)
    assert result.decision == DecisionEnum.shortlisted, (
        f"Case D: Expected shortlisted for AI/ML role. Got: {result.decision}. Score={result.score}"
    )


@pytest.mark.asyncio
async def test_case_d_neural_networks_met():
    result = await get_result("d", JOB_D)
    c = find_criterion(result, "Neural Networks")
    assert c is not None, f"Case D: Neural Networks not evaluated."
    assert c.status == CriterionStatusEnum.met, f"Case D: Neural Networks should be met. Got: {c.status}"
    assert len(c.evidence_refs) > 0, "Case D: Neural Networks needs evidence_refs"


@pytest.mark.asyncio
async def test_case_d_computer_vision_met():
    result = await get_result("d", JOB_D)
    c = find_criterion(result, "Computer Vision")
    assert c is not None, f"Case D: Computer Vision not evaluated."
    assert c.status == CriterionStatusEnum.met, f"Case D: Computer Vision should be met. Got: {c.status}"


# ===========================================================================
# Case E: Education requirement
# ===========================================================================

@pytest.mark.asyncio
async def test_case_e_cs_degree_evaluated():
    result = await get_result("e", JOB_E)
    c = find_criterion(result, "Computer Science")
    assert c is not None, (
        f"Case E: CS degree not evaluated. Criteria: {[c.label for c in result.criteria]}"
    )


@pytest.mark.asyncio
async def test_case_e_does_not_fabricate_graduation():
    """Model must not claim the degree is complete when source says 'Present'."""
    result = await get_result("e", JOB_E)
    all_text = " ".join(
        result.reasons + result.strengths + result.weaknesses + result.missingInformation
    ).lower()
    # Hard fail: if the model explicitly says "graduated" or "completed" without qualification
    FABRICATED_CLAIMS = ["has graduated", "already graduated", "degree completed", "degree is complete"]
    found = [claim for claim in FABRICATED_CLAIMS if claim in all_text]
    assert not found, (
        f"Case E: Model fabricated completion of degree (source says 'Present'): {found}"
    )
