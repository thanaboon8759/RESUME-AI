import pytest
import re
import asyncio
from dotenv import load_dotenv
load_dotenv() # Load API keys BEFORE importing services

from app.services.resume_extraction_service import analyze_resume_facts_with_qwen
from app.services.screening_service import screen_candidate_with_qwen
from app.schemas.job import Job
from app.schemas.core import DecisionEnum


def normalize_evidence_text(text: str) -> str:
    """Collapse all whitespace sequences (newlines, tabs, multiple spaces) into
    a single space and strip surrounding whitespace.  Meaningful characters
    (Thai, English, punctuation, digits) are preserved."""
    return re.sub(r"\s+", " ", text).strip()


def evidence_exists(quote: str, source_text: str) -> bool:
    """Return True if the whitespace-normalized quote is a substring of the
    whitespace-normalized source text."""
    return normalize_evidence_text(quote) in normalize_evidence_text(source_text)

SCENARIOS = [
    {
        "name": "Scenario 1 - Strong Match",
        "job": {
            "id": "job1",
            "title": "AI Developer",
            "jd": "We need an AI Developer.",
            "required": ["Python", "FastAPI", "REST API", "Machine Learning", "1+ year software development experience"],
            "preferred": ["Docker", "AWS", "OpenCV"],
            "weights": {"Python": 3, "FastAPI": 3, "REST API": 3, "Machine Learning": 3, "1+ year software development experience": 3},
            "experience": "1+",
            "education": "BS",
            "location": "Bangkok",
            "salary": "N/A",
            "mandatory": ["Python"]
        },
        "resume_text": (
            "John Doe\n"
            "AI Developer\n"
            "Experience:\n"
            "- Software Engineer at AI Tech (Jan 2022 - Present). 2+ years of experience.\n"
            "  Built REST APIs using FastAPI and Python.\n"
            "  Implemented Machine Learning models and Computer Vision tasks using OpenCV.\n"
            "  Deployed applications using Docker and AWS.\n"
        ),
        "expected": {
            "decision_pass": True,
            "score_min": 80,
            "matched_reqs": ["Python", "FastAPI", "Machine Learning"],
            "matched_prefs": ["Docker", "AWS", "OpenCV"]
        }
    },
    {
        "name": "Scenario 2 - Missing Required Skill",
        "job": {
            "id": "job2",
            "title": "Backend Developer",
            "jd": "Backend Developer",
            "required": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            "preferred": ["AWS", "Redis"],
            "weights": {"PostgreSQL": 5},
            "experience": "1+", "education": "", "location": "", "salary": "", "mandatory": ["PostgreSQL"]
        },
        "resume_text": (
            "Jane Smith\n"
            "Backend Developer\n"
            "Experience:\n"
            "- Web Dev at Startup X (2021-2023).\n"
            "  Developed backend systems using Python and FastAPI. Packaged apps with Docker.\n"
            "  (Notice no PostgreSQL or database experience mentioned)\n"
        ),
        "expected": {
            "decision_pass": False,
            "matched_reqs": ["Python", "FastAPI", "Docker"],
            "unmatched_reqs": ["PostgreSQL"],
            "check_reason_mentions": "PostgreSQL"
        }
    },
    {
        "name": "Scenario 3 - Insufficient Experience",
        "job": {
            "id": "job3",
            "title": "Senior Backend Developer",
            "jd": "Senior role",
            "required": ["Python", "FastAPI", "3+ years professional backend development"],
            "preferred": ["Docker", "AWS"],
            "weights": {}, "experience": "3+", "education": "", "location": "", "salary": "", "mandatory": ["3+ years professional backend development"]
        },
        "resume_text": (
            "Alice Johnson\n"
            "Experience:\n"
            "- Junior Developer at CodeCorp (Jan 2023 - Dec 2023). 1 year professional experience.\n"
            "  Worked with Python, FastAPI, and Docker.\n"
        ),
        "expected": {
            "decision_pass": False,
            "matched_reqs": ["Python", "FastAPI"],
            "unmatched_reqs": ["3+ years professional backend development"],
            "matched_prefs": ["Docker"],
            "unmatched_prefs": ["AWS"]
        }
    },
    {
        "name": "Scenario 4 - Strong Match with Preferred Skills",
        "job": {
            "id": "job4",
            "title": "AI/Computer Vision Developer",
            "jd": "CV role",
            "required": ["Python", "OpenCV", "Machine Learning", "Computer Vision"],
            "preferred": ["FastAPI", "Docker", "AWS"],
            "weights": {}, "experience": "", "education": "", "location": "", "salary": "", "mandatory": []
        },
        "resume_text": (
            "Bob Lee\n"
            "Experience:\n"
            "- ML Engineer (2020-Present). Specialized in Computer Vision and Machine Learning.\n"
            "  Extensive use of Python and OpenCV for image processing.\n"
            "  Served models using FastAPI. Containerized with Docker and hosted on AWS.\n"
        ),
        "expected": {
            "decision_pass": True,
            "score_min": 85,
            "matched_reqs": ["Python", "OpenCV", "Machine Learning", "Computer Vision"],
            "matched_prefs": ["FastAPI", "Docker", "AWS"]
        }
    },
    {
        "name": "Scenario 5 - Thai Resume + English Job",
        "job": {
            "id": "job5",
            "title": "AI Developer",
            "jd": "AI Dev",
            "required": ["Python", "FastAPI", "Machine Learning", "1+ year development experience"],
            "preferred": ["Docker", "AWS"],
            "weights": {}, "experience": "", "education": "", "location": "", "salary": "", "mandatory": []
        },
        "resume_text": (
            "ประยุทธ์ จันทร์โอชา\n"
            "ข้อมูลการทำงาน:\n"
            "- นักพัฒนาซอฟต์แวร์ (พ.ศ. 2565 - ปัจจุบัน) มีประสบการณ์พัฒนา Software ตั้งแต่ 2022 (มากกว่า 1 ปี)\n"
            "  พัฒนา Backend ด้วย Python และสร้าง REST API ด้วย FastAPI\n"
            "  มีประสบการณ์ด้าน Machine Learning\n"
        ),
        "expected": {
            "decision_pass": True,
            "matched_reqs": ["Python", "FastAPI", "Machine Learning", "1+ year development experience"]
        }
    },
    {
        "name": "Scenario 6 - Mixed Thai + English Resume",
        "job": {
            "id": "job6",
            "title": "Software Engineer",
            "jd": "Dev",
            "required": ["React", "Node.js", "Teamwork"],
            "preferred": [],
            "weights": {}, "experience": "", "education": "", "location": "", "salary": "", "mandatory": []
        },
        "resume_text": (
            "Somchai Jaidee\n"
            "Education: Chulalongkorn University, BS Computer Engineering (English Program)\n"
            "ประสบการณ์การทำงาน:\n"
            "- Web Developer ที่บริษัท ABC (2021-2023)\n"
            "  พัฒนาระบบด้วย React และ Node.js\n"
            "  ทำงานร่วมกับทีม (Teamwork) ขนาด 10 คนได้อย่างมีประสิทธิภาพ\n"
        ),
        "expected": {
            "decision_pass": True,
            "matched_reqs": ["React", "Node.js", "Teamwork"]
        }
    },
    {
        "name": "Scenario 7 - No Required Skills",
        "job": {
            "id": "job7",
            "title": "DevOps Engineer",
            "jd": "DevOps",
            "required": ["Kubernetes", "Terraform", "CI/CD"],
            "preferred": [],
            "weights": {}, "experience": "", "education": "", "location": "", "salary": "", "mandatory": []
        },
        "resume_text": (
            "David Clark\n"
            "Experience:\n"
            "- Graphic Designer (2018-2024)\n"
            "  Designed logos using Photoshop and Illustrator.\n"
        ),
        "expected": {
            "decision_pass": False,
            "score_max": 40,
            "unmatched_reqs": ["Kubernetes", "Terraform", "CI/CD"]
        }
    },
    {
        "name": "Scenario 8 - Project vs Professional Experience",
        "job": {
            "id": "job8",
            "title": "Python Developer",
            "jd": "Backend",
            "required": ["2+ years professional Python experience"],
            "preferred": [],
            "weights": {}, "experience": "2+", "education": "", "location": "", "salary": "", "mandatory": ["2+ years professional Python experience"]
        },
        "resume_text": (
            "Eva Green\n"
            "Education: BS Computer Science (Graduated 2024)\n"
            "Projects:\n"
            "- University Capstone (2022-2024): 2 years of Python project development.\n"
            "Experience:\n"
            "- Cashier at Starbucks (2021-2022).\n"
        ),
        "expected": {
            "decision_pass": False,
            "unmatched_reqs": ["2+ years professional Python experience"],
            "check_reason_mentions": "professional" # Should distinguish project from professional
        }
    }
]

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
async def test_ai_screening_scenario(scenario):
    # 1. Resume Extraction
    profile = await analyze_resume_facts_with_qwen(scenario["resume_text"], "Test Candidate")
    
    # 2. Assert Qwen #1 facts only
    assert not hasattr(profile, "score")
    assert not hasattr(profile, "decision")
    
    # 3. Screening
    job = Job(**scenario["job"])
    result = await screen_candidate_with_qwen(profile, job)
    
    expected = scenario["expected"]
    
    # Check Decision
    if "decision_pass" in expected:
        is_pass = result.decision == DecisionEnum.shortlisted
        assert is_pass == expected["decision_pass"], f"Expected pass={expected['decision_pass']}, got {result.decision}. Reasons: {result.reasons}"
        
    # Check Score Min/Max
    if "score_min" in expected:
        assert result.score >= expected["score_min"], f"Score {result.score} < min {expected['score_min']}"
    if "score_max" in expected:
        assert result.score <= expected["score_max"], f"Score {result.score} > max {expected['score_max']}"
        
    # Check Matched Criteria
    evaluated_labels = {c.label: c for c in result.criteria}
    
    def normalize_str(s):
        return s.lower().replace(" ", "")
        
    def find_criterion(req_name):
        # Allow partial label match (e.g. "PostgreSQL" might be output as "PostgreSQL Experience")
        for label, c in evaluated_labels.items():
            if normalize_str(req_name) in normalize_str(label):
                return c
            # also check if the label in the evaluation matches the required word
            if req_name.lower() in label.lower():
                return c
        return None

    if "matched_reqs" in expected:
        for req in expected["matched_reqs"]:
            c = find_criterion(req)
            assert c is not None, f"Criterion '{req}' not evaluated by AI. Evaluated: {list(evaluated_labels.keys())}"
            assert c.status.value == "met", f"Expected '{req}' to be 'met', got {c.status.value}"
            
            # Evidence validation: if met, it MUST have evidence_refs pointing to profile
            assert len(c.evidence_refs) > 0, f"Matched criterion '{req}' has no evidence_refs!"
            for ref in c.evidence_refs:
                # Find the ref in the profile
                sanitized_field = ref.field.split('[')[0].split('.')[0]
                field_data = getattr(profile, sanitized_field, None)
                assert field_data is not None, f"Field '{sanitized_field}' not found in profile (original: {ref.field})"
                
                # Check that the value exists and has evidence attached
                found_match = False
                if isinstance(field_data, list):
                    for item in field_data:
                        if isinstance(item, dict):
                            for k, v in item.items():
                                if k == "evidence":
                                    continue
                                
                                # Handle both strings and lists of strings (like responsibilities)
                                values_to_check = v if isinstance(v, list) else [v]
                                for val in values_to_check:
                                    if isinstance(val, str) and (ref.value.lower() in val.lower() or val.lower() in ref.value.lower()):
                                        found_match = True
                                        assert "evidence" in item, f"No evidence attached to field {ref.field} item {item}"
                                        quote = item["evidence"]["quote"]
                                        assert evidence_exists(quote, scenario["resume_text"]), (
                                            f"Quote '{quote}' hallucinated! Not found (even after whitespace normalization) in resume."
                                        )
                                        assert "Skills:" not in quote, f"Quote '{quote}' contains synthesized text 'Skills:'"
                        elif hasattr(item, "name"):
                            if item.name.lower() == ref.value.lower() or ref.value.lower() in item.name.lower():
                                found_match = True
                                assert getattr(item, "evidence", None) is not None, f"No evidence attached to skill {item.name}"
                                quote = item.evidence.quote
                                assert evidence_exists(quote, scenario["resume_text"]), (
                                    f"Quote '{quote}' hallucinated! Not found (even after whitespace normalization) in resume."
                                )
                                assert "Skills:" not in quote, f"Quote '{quote}' contains synthesized text 'Skills:'"
                if not found_match:
                    print(f"FAILED TO MATCH: ref.value='{ref.value}', field_data={field_data}")
                assert found_match, f"Value '{ref.value}' not found in profile field '{ref.field}'"

    if "unmatched_reqs" in expected:
        for req in expected["unmatched_reqs"]:
            c = find_criterion(req)
            # It might be unmet or not even listed, both are acceptable as failure
            if c is not None:
                assert c.status.value == "unmet", f"Expected '{req}' to be 'unmet', got {c.status.value}"
                
    if "check_reason_mentions" in expected:
        mention = expected["check_reason_mentions"].lower()
        reason_text = " ".join(result.reasons).lower()
        assert mention in reason_text, f"Expected reasons to mention '{mention}', but got: {reason_text}"

