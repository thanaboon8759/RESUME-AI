import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from models import CandidateCreate, Candidate, DumbdogAIResponse, DecisionEnum, CriterionStatusEnum
from dumbdog_service import dumbdog_client
from database import supabase

app = FastAPI(title="DumbdogAI Backend")

# Allow requests from the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def create_rich_candidate(candidate_id: str, create_data: CandidateCreate, ai_data: DumbdogAIResponse) -> Candidate:
    """Map simplified AI data to the rich Candidate structure expected by the frontend"""
    # Create generic mock criteria based on reasons
    criteria = []
    for i, reason in enumerate(ai_data.reasons):
        criteria.append({
            "id": f"crit-{i}",
            "label": reason,
            "status": CriterionStatusEnum.met,
            "weight": 3,
            "mandatory": False,
            "evidence": []
        })
        
    return Candidate(
        id=candidate_id,
        name=create_data.name,
        englishName=create_data.name, # mock
        initials="".join([n[0] for n in create_data.name.split() if n]),
        role="Unknown", # mock
        headline="Evaluated by DumbdogAI",
        score=ai_data.score,
        experience="Unknown",
        location="Unknown",
        resumeUrl="",
        extractedText=create_data.resume_text,
        parseStatus="done",
        failureReason=None,
        hasBlocker=False,
        duplicateOf=None,
        criteria=criteria,
        strengths=ai_data.reasons,
        weaknesses=[],
        missingInformation=[],
        detectedLanguages=["Thai", "English"],
        decision=ai_data.decision
    )

@app.post("/api/candidates", response_model=Candidate)
async def create_candidate(candidate_data: CandidateCreate):
    # 1. Evaluate with DumbdogAI (Mock)
    try:
        ai_evaluation = await dumbdog_client.evaluate_candidate(
            candidate_name=candidate_data.name,
            position="Backend Developer", # Defaulting for now
            resume_text=candidate_data.resume_text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Evaluation failed: {str(e)}")

    # 2. Prepare data structures
    candidate_id = str(uuid.uuid4())
    rich_candidate = create_rich_candidate(candidate_id, candidate_data, ai_evaluation)
    
    # 3. Save to Supabase
    if supabase:
        try:
            db_record = {
                "id": candidate_id,
                "candidate_name": candidate_data.name,
                "position": "Backend Developer",
                "score": ai_evaluation.score,
                "decision": ai_evaluation.decision.value,
                "reason": ai_evaluation.reasons,
                "full_data": rich_candidate.model_dump(mode="json")
            }
            supabase.table("candidates").insert(db_record).execute()
        except Exception as e:
            # If table doesn't exist, log it but return the data to the frontend anyway for local dev
            print(f"Supabase insert failed (check schema): {e}")
            # Depending on strictness, we might raise an error here
            # raise HTTPException(status_code=500, detail=f"Database insert failed: {str(e)}")
            
    # 4. Return the detailed structure to the frontend
    return rich_candidate


@app.get("/api/candidates", response_model=List[Candidate])
async def get_candidates():
    if not supabase:
        # Fallback to empty list or dummy data if DB is not connected
        return []
        
    try:
        response = supabase.table("candidates").select("full_data").execute()
        # Extract the rich frontend data from the JSONB column
        candidates = [row["full_data"] for row in response.data]
        return candidates
    except Exception as e:
        print(f"Supabase fetch failed: {e}")
        return []

@app.get("/api/candidates/{candidate_id}", response_model=Candidate)
async def get_candidate(candidate_id: str):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
        
    try:
        response = supabase.table("candidates").select("full_data").eq("id", candidate_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return response.data[0]["full_data"]
    except Exception as e:
        print(f"Supabase fetch failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

@app.post("/api/seed")
async def seed_database():
    """Endpoint to trigger the database seeding process manually via API."""
    try:
        import seed_db
        seed_db.seed()
        return {"status": "success", "message": "Database seeded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Seeding failed: {str(e)}")
