# DUMB DOG AI

An intelligent recruitment and candidate evaluation platform.

## Tech Stack

* **Frontend:** React, Tailwind CSS
* **Backend:** FastAPI (Python)
* **Database:** Supabase (PostgreSQL)
* **Infrastructure:** Cloudflare
* **AI:** LLM API, Embedding Model
* **Document Processing:** PyMuPDF, python-docx, PaddleOCR
* **Vector Search:** pgvector

## Local Development Setup

### 1. Backend Setup
1. Navigate to the `DUMB-DOG-AI` directory.
2. Create a `.env` file based on the required environment variables:
   ```env
   SUPABASE_URL=https://<your-project-id>.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
   ```
3. Initialize the database by running `schema.sql` in your Supabase SQL Editor.
4. Activate the virtual environment and start the FastAPI server:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   uvicorn main:app --reload
   ```

### 2. Frontend Setup
1. Navigate to the `frontend` directory.
2. Start the Vite development server:
   ```powershell
   npm run dev
   ```
3. The frontend will be available at `http://localhost:5173`.
