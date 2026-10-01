from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import preferences, jobs, candidates, decisions, uploads

app = FastAPI(title="DumbdogAI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(preferences.router, prefix="/api/preferences", tags=["Preferences"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
# We route /api/jobs/{job_id}/candidates through candidates router, and /api/candidates
app.include_router(candidates.router, prefix="/api", tags=["Candidates"])
app.include_router(decisions.router, prefix="/api/decisions", tags=["Decisions"])
# Uploads handles /api/jobs/{job_id}/uploads and /api/uploads
app.include_router(uploads.router, prefix="/api", tags=["Uploads"])
