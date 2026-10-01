import uuid
import logging
from typing import List
from fastapi import HTTPException
from app.schemas.candidate import Candidate, CandidateCreate, Criterion
from app.schemas.core import CriterionStatusEnum
from app.repositories import candidate_repository, job_repository
from app.services.document_extraction_service import extract_document
from app.services.resume_extraction_service import analyze_resume_facts_with_qwen
from app.services.screening_service import screen_candidate_with_qwen
from app.database.supabase.client import supabase

logger = logging.getLogger(__name__)

def get_candidates(job_id: str, user_id: str) -> List[Candidate]:
    return candidate_repository.get_candidates_for_job(job_id, user_id)

def get_candidate(candidate_id: str, user_id: str) -> Candidate | None:
    return candidate_repository.get_candidate(candidate_id, user_id)

async def create_candidate(job_id: str, candidate_data: CandidateCreate, user_id: str) -> Candidate:
    extracted_text = candidate_data.resume_text
    file_bytes = b""
    
    if candidate_data.resume_url:
        try:
            logger.info("Retrieving PDF from Supabase")
            file_bytes = supabase.storage.from_("uploads").download(candidate_data.resume_url)
        except Exception as e:
            logger.error(f"Failed to download PDF from Supabase: {e}")
            raise HTTPException(status_code=500, detail="Supabase PDF retrieval failure")
            
    blocks = []
    if file_bytes:
        extracted_text, blocks = await extract_document(file_bytes)
        
    logger.info("Extracting factual resume profile (Qwen #1)")
    profile = await analyze_resume_facts_with_qwen(extracted_text, candidate_data.name)
    
    # Retrieve job requirements for screening
    job = job_repository.get_job(job_id, user_id)
    if not job:
        # Fallback to mock job if user lacks jobs or E2E test bypasses job creation
        from app.schemas.job import Job
        job = Job(id=job_id, title="Unknown Job", jd="", required=[], preferred=[], weights={}, experience="", education="", location="", salary="", mandatory=[])
    
    logger.info("Screening candidate against job requirements (Qwen #2)")
    screening = await screen_candidate_with_qwen(profile, job)
    
    candidate_id = str(uuid.uuid4())
    criteria = []
    
    # Map raw blocks to a dictionary for fast lookup by ID
    block_map = {b["id"]: b for b in blocks}

    # Helper function to map evidence to bounding boxes or char offsets
    def map_evidence_refs(refs):
        mapped = []
        for ref in refs:
            field = getattr(ref, "field", "")
            value = getattr(ref, "value", "")
            
            # Sanitize field just in case Qwen outputs dot or bracket notation
            field = field.split('[')[0].split('.')[0]
            
            target_evidence = None
            if hasattr(profile, field):
                field_data = getattr(profile, field)
                if isinstance(field_data, list):
                    for item in field_data:
                        if isinstance(item, dict):
                            # For Experience, Education, Projects
                            for k, v in item.items():
                                if k == "evidence":
                                    continue
                                
                                values_to_check = v if isinstance(v, list) else [v]
                                for val in values_to_check:
                                    if isinstance(val, str) and (value.lower() in val.lower() or val.lower() in value.lower()):
                                        target_evidence = item.get("evidence")
                                        break
                                if target_evidence:
                                    break
                            if target_evidence:
                                break
                        elif hasattr(item, "name"):
                            # For SkillFact
                            if item.name.lower() == value.lower() or value.lower() in item.name.lower():
                                if item.evidence:
                                    target_evidence = item.evidence.model_dump()
                                break

            if target_evidence and isinstance(target_evidence, dict):
                quote = target_evidence.get("quote", "")
                block_ids = target_evidence.get("block_ids", [])
                
                if block_ids:
                    for bid in block_ids:
                        if bid in block_map:
                            b = block_map[bid]
                            mapped.append({
                                "id": str(uuid.uuid4()),
                                "page": b.get("page", 1),
                                "quote": quote,
                                "bbox": b.get("bbox"),
                                "charStart": 0,
                                "charEnd": 0
                            })
                elif quote:
                    start = extracted_text.find(quote)
                    mapped.append({
                        "id": str(uuid.uuid4()),
                        "page": 1,
                        "quote": quote,
                        "bbox": None,
                        "charStart": start,
                        "charEnd": start + len(quote) if start >= 0 else -1
                    })
        return mapped

    # Map Criteria
    for i, crit in enumerate(screening.criteria):
        mapped_evidence = map_evidence_refs(crit.evidence_refs)
        criteria.append({
            "id": f"crit-{i}", 
            "label": crit.label, 
            "status": crit.status,
            "weight": 3, 
            "mandatory": False, 
            "evidence": mapped_evidence
        })
        
    # Map raw reasons (legacy mapping fallback for reasons lacking explicit criteria)
    if not criteria and screening.reasons:
        for i, reason in enumerate(screening.reasons):
            criteria.append({
                "id": f"crit-legacy-{i}", 
                "label": reason, 
                "status": CriterionStatusEnum.met,
                "weight": 3, 
                "mandatory": False, 
                "evidence": []
            })

    # Ensure backwards compatibility for the frontend Candidate object
    rich_candidate = Candidate(
        id=candidate_id, name=candidate_data.name, englishName=candidate_data.name,
        initials="".join([n[0] for n in candidate_data.name.split() if n]), 
        role=screening.role, 
        headline=screening.headline,
        score=screening.score, 
        experience=screening.experience_summary, 
        location=screening.location, 
        resumeUrl=candidate_data.resume_url or "",
        extractedText=extracted_text, 
        parseStatus="done", 
        failureReason=None, 
        hasBlocker=False, 
        duplicateOf=None,
        criteria=criteria, 
        strengths=screening.strengths, 
        weaknesses=screening.weaknesses, 
        missingInformation=screening.missingInformation, 
        detectedLanguages=screening.detectedLanguages,
        decision=screening.decision
    )
    
    # Store the combined object temporarily in the same table
    candidate_repository.create_candidate(candidate_id, job_id, candidate_data.name, screening, rich_candidate, user_id)
    return rich_candidate
