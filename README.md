# DUMB DOG AI - Backend

An intelligent recruitment and candidate evaluation platform designed to help HR teams parse, analyze, and rank candidate resumes using AI.

## Key Features

- **AI-Powered Resume Parsing**: Automatically extracts text and insights from uploaded PDF/DOCX resumes.
- **Candidate Evaluation**: Ranks candidates based on job descriptions (JD), tracking matching criteria and identifying missing information.
- **Decision Workspace**: Allows HR to shortlist, reject, or mark candidates as undecided, with customizable reasoning.
- **Secure Storage & Authentication**: Integrates with Supabase for user authentication, PostgreSQL database, and cloud storage for resume files.
- **RESTful API**: Built with FastAPI, providing robust and fast endpoints for the frontend workspace.

## Tech Stack

* **Framework:** FastAPI (Python)
* **Database & Auth:** Supabase (PostgreSQL, GoTrue)
* **Storage:** Supabase Storage (Buckets)
* **AI & Parsing:** LLM API, PyMuPDF, python-docx, PaddleOCR
* **Vector Search:** pgvector

## Local Development Setup

### 1. Prerequisites
- Python 3.10+
- Supabase project (URL and Service Role Key)

### 2. Environment Configuration
Navigate to the `backend` directory and create a `.env` file based on your Supabase credentials:
```env
SUPABASE_URL=https://<your-project-id>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
```

### 3. Database Initialization
Ensure your Supabase project is set up with the required tables:
- `users`, `preferences`, `jobs`, `candidates`, `decisions`, `uploads`
- Also, create a **Storage Bucket** named `uploads` (must be public or accessible via RLS).
Run `schema.sql` (if available) in your Supabase SQL Editor.

### 4. Running the Server
Activate the virtual environment and start the FastAPI development server:
```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```
The API documentation will be available at `http://localhost:8000/docs`.

## Testing

The project uses `pytest` for unit testing. To run the test suite:
```powershell
pytest
```
This will discover and run all tests in the `tests/` directory (e.g., `test_main.py`, `test_jobs.py`).
