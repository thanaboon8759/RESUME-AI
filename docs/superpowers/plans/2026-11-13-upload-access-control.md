# Upload Access Control and Local OCR Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop one signed-in user from reading, overwriting or screening another user's resumes, and close the local-OCR gaps deferred from PR 5.

**Architecture:** The backend uses the Supabase service-role key, so Row Level Security does not apply and every query must filter by `user_id` itself. Ownership checks go in the API and service layers through one new repository read, `upload_repository.get_upload`. The local OCR fixes stay inside `extract_text_local`.

**Tech Stack:** FastAPI, Supabase Python client, PyMuPDF, httpx, pytest-asyncio (`asyncio_mode = auto`).

**Spec:** None written. This plan comes from a code read on 2026-11-13; the defects below are the spec.

## Context: defects found on `main` (3dcc6e3)

1. `GET /api/uploads/{upload_id}/download` (`app/api/uploads.py:42-57`) looks up the upload by id only, so any signed-in user can download any resume. Its own 404 is also caught by `except Exception` and turned into a 500.
2. `POST /api/uploads/file` (`app/api/uploads.py:23-40`):
   - It doesn't check that `jobId` belongs to the caller.
   - It puts the raw `file.filename` and `id` into the storage path, so a `/` or `..` can reach another folder.
   - It reads files of any size into memory.
3. `PUT /api/uploads/{upload_id}` upserts by the id in the request body, ignores the path id, and writes the caller's `user_id`. So any user can take over any upload row.
4. `create_candidate` (`app/services/candidate_service.py:22-36`) downloads whatever storage path is in `resume_url`, so a user can screen another user's resume.
5. Deferred from PR 5, in `extract_text_local` (`app/services/document_extraction_service.py:139-174`):
   - Malformed JSON such as `{"natural_text": "abc` is passed through as text, braces included.
   - A JSON object without `natural_text`/`text` turns a page into `""`, so the page silently vanishes from a multi-page document.
   - Page rendering runs on the event loop.
   - The PDF is never closed.
   - The README doesn't document the OCR variables.

## Global Constraints

- Work on branch `fix/upload-access-control`, which branches from `origin/main` at 3dcc6e3.
- A resource that exists but belongs to someone else returns **404**, never 403, so ids can't be probed.
- `MAX_UPLOAD_BYTES = 20 * 1024 * 1024`, a 20 MB upload limit. A real Thai scan in testing was 11.6 MB. Over the limit returns **413**.
- Storage path segments (`id`, filename) must match `^[\w.\- ]+$`, must not be `.` or `..`, and must not contain `/` or `\`. Otherwise the request returns **400**.
- Keep the existing layering, API → service → repository. Don't add dependencies.
- Offline suite command: `pytest --ignore=tests/test_real_resume_validation.py --ignore=tests/test_screening_scenarios.py -q`. It has 79 passing tests at the start and must have 0 failures at the end.

## Review Focus

1. **Uploading again to the same id must keep working.** The current upsert creates or replaces the row, and the frontend may rely on that. `update_upload` must still create a row whose id doesn't exist yet. (Task 2 test: `test_update_creates_new_row`.)
2. **The candidate E2E fallback must not break.** `create_candidate` with `resume_text` and no `resume_url` still runs when the job doesn't exist. (Task 3 test: `test_text_only_candidate_skips_ownership`.)
3. **Thai filenames are legitimate.** `\w` in Python `re` is Unicode, so `เรซูเม่.pdf` must pass the segment check. (Task 1 test: `test_thai_filename_allowed`.)
4. **A file exactly at the limit is accepted.** Read `MAX_UPLOAD_BYTES + 1` bytes and reject only when more than `MAX_UPLOAD_BYTES` came back. (Task 1 test: `test_upload_size_limit`.)
5. **One page with no text must fail the whole document,** not vanish while the others are joined. (Task 4 test: `test_local_ocr_rejects_page_without_text`.)

---

### Task 1: Upload and download endpoints check ownership

**Files:**
- Modify: `app/repositories/upload_repository.py` (add `get_upload`)
- Modify: `app/api/uploads.py:23-57`
- Test: `tests/test_uploads_api.py` (new)

**Interfaces:**
- Produces: `upload_repository.get_upload(upload_id: str) -> dict | None`. It returns the row's `{"id", "job_id", "user_id", "name"}`, or `None` if there's no row. It does **not** filter by user; callers compare `user_id`. Use `.execute()` and `res.data[0]`, not `.single()`, which raises on 0 rows.
- Produces: `MAX_UPLOAD_BYTES` and `_safe_segment(value: str) -> bool` in `app/api/uploads.py`.

- [ ] **Step 1: Write the failing tests** in `tests/test_uploads_api.py`. Use the same setup as `tests/test_jobs.py`: a `MockUser` with id `"u1"`, `app.dependency_overrides[get_current_user]`, and `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`. Monkeypatch `app.api.uploads.upload_repository.get_upload`, `app.api.uploads.job_repository.get_job` and `app.api.uploads.supabase` (a `MagicMock`).

```python
async def test_download_other_users_upload_is_404(...):
    get_upload -> {"id": "x", "job_id": "j", "user_id": "someone-else", "name": "a.pdf"}
    r = await ac.get("/api/uploads/x/download");  assert r.status_code == 404
    storage download never called

async def test_download_own_upload(...):
    get_upload -> {..., "user_id": "u1"};  storage download returns b"%PDF"
    r.status_code == 200 and r.content == b"%PDF"
    storage path == "j/x_a.pdf"

async def test_download_missing_is_404(...):          get_upload -> None;  404 (not 500)

async def test_upload_to_other_users_job_is_404(...): get_job -> None;  POST /api/uploads/file -> 404, nothing stored

async def test_upload_rejects_path_segments(...):     filename "../x.pdf" -> 400;  form id "a/b" -> 400

async def test_thai_filename_allowed(...):            filename "เรซูเม่.pdf", get_job -> a Job -> 200

async def test_upload_size_limit(...):                MAX_UPLOAD_BYTES bytes -> 200;  MAX_UPLOAD_BYTES + 1 -> 413
```

Patch `MAX_UPLOAD_BYTES` to 10 inside the size test so it doesn't allocate 20 MB.

- [ ] **Step 2: Run it to make sure it fails**

Run: `pytest tests/test_uploads_api.py -v`
Expected: FAIL. `get_upload` doesn't exist yet, the download returns the other user's file, and oversized and path-segment uploads still succeed.

- [ ] **Step 3: Implement `get_upload` and fix both endpoints**
  - **Imports:** add `from app.repositories import job_repository, upload_repository` to `app/api/uploads.py`. The tests patch both names on that module.
  - **Download:** call `get_upload`. If it returns `None` or the row's `user_id != user.id`, raise 404.
  - **Upload:** check `job_repository.get_job(jobId, user.id)` first; if it returns `None`, raise 404. Check `_safe_segment(id)` and `_safe_segment(file.filename)`; if either fails, raise 400. Then `content = await file.read(MAX_UPLOAD_BYTES + 1)`; if `len(content) > MAX_UPLOAD_BYTES`, raise 413.
  - **In both handlers:** add `except HTTPException: raise` before `except Exception`, so 4xx responses aren't turned into 500.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `pytest tests/test_uploads_api.py -v`, then the offline suite.
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/repositories/upload_repository.py app/api/uploads.py tests/test_uploads_api.py
git commit -m "Check ownership, path and size on upload and download"
```

### Task 2: Upload row updates can't take over another user's row

**Files:**
- Modify: `app/services/upload_service.py` (`update_upload`)
- Test: `tests/test_uploads_api.py`

**Interfaces:**
- Consumes: `upload_repository.get_upload(upload_id) -> dict | None` from Task 1.
- `upload_service.update_upload(upload_id: str, upload: Upload, user_id: str) -> None` keeps its signature. It raises `HTTPException(404)` when the row exists and belongs to another user. Before calling `upload_repository.update_upload`, it sets `upload.id = upload_id`, so the path id wins over the body id.

- [ ] **Step 1: Write the failing tests**

```python
async def test_update_other_users_row_is_404(...):
    get_upload -> {"user_id": "someone-else", ...};  PUT /api/uploads/x -> 404;  repository update not called

async def test_update_creates_new_row(...):
    get_upload -> None;  PUT /api/uploads/x with body id "x" -> 200;  repository update called once

async def test_update_uses_path_id(...):
    get_upload -> {"user_id": "u1", ...};  PUT /api/uploads/x with body id "y" -> 200
    the Upload passed to the repository has id == "x"
```

Monkeypatch `app.services.upload_service.upload_repository.get_upload` and `.update_upload`.

- [ ] **Step 2: Run them to make sure they fail**

Run: `pytest tests/test_uploads_api.py -k update -v`
Expected: FAIL. The other user's row is updated, and the body id is used.

- [ ] **Step 3: Implement the ownership check and the path-id override in `update_upload`**

- [ ] **Step 4: Run the tests and make sure they pass:** `pytest tests/test_uploads_api.py -v`, then the offline suite.

- [ ] **Step 5: Commit**

```bash
git add app/services/upload_service.py tests/test_uploads_api.py
git commit -m "Refuse upload row updates on another user's upload"
```

### Task 3: Candidates can only be created from the caller's own resumes

**Files:**
- Modify: `app/services/candidate_service.py:22-36`
- Test: `tests/test_candidate_service.py`

**Interfaces:**
- `create_candidate(job_id, candidate_data, user_id)` keeps its signature. When `candidate_data.resume_url` is set:
  - It raises `HTTPException(404, "Resume not found")` unless `job_repository.get_job(job_id, user_id)` returns a job **and** `resume_url.startswith(f"{job_id}/")`.
  - It runs this check before the storage download.
  - Storage paths are `{jobId}/{id}_{filename}`, from Task 1.

- [ ] **Step 1: Write the failing tests.** Use the existing `SVC` patch style and `make_job()`. Patch `f"{SVC}.supabase"` with a `MagicMock`.

```python
async def test_resume_from_other_job_is_404():
    get_job -> make_job() (id "job1");  resume_url "otherjob/x_a.pdf"
    raises HTTPException with status_code 404;  storage download not called

async def test_resume_for_unowned_job_is_404():
    get_job -> None;  resume_url "job1/x_a.pdf"  -> 404;  storage download not called

async def test_text_only_candidate_skips_ownership():
    get_job -> None;  resume_url None;  resume_text "..."
    returns a Candidate (same as test_create_candidate_unknown_job)
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `pytest tests/test_candidate_service.py -v`
Expected: the first two FAIL because the download happens, and the third passes.

- [ ] **Step 3: Implement the check in `create_candidate`**

- [ ] **Step 4: Run the tests and make sure they pass:** `pytest tests/test_candidate_service.py -v`, then the offline suite.

- [ ] **Step 5: Commit**

```bash
git add app/services/candidate_service.py tests/test_candidate_service.py
git commit -m "Only screen resumes stored under the caller's own job"
```

### Task 4: Local OCR rejects bad pages, renders off the event loop, and is documented

**Files:**
- Modify: `app/services/document_extraction_service.py:139-174`
- Modify: `README.md`, section "2. Environment Configuration"
- Test: `tests/test_local_ocr.py`

**Interfaces:**
- `extract_text_local(file_bytes: bytes) -> str` keeps its signature and its `"OCR processing error: …"` wrapping.
- New private helper `_render_pages(file_bytes: bytes) -> list[bytes]` returns PNG bytes per page. It opens the document with `with fitz.open(...) as doc:` and applies the page cap and dpi rule. Call it through `await asyncio.to_thread(_render_pages, file_bytes)`.

Page reply rules, in this order:
1. Content that starts with `{` after `lstrip()` and fails `json.loads` raises `ValueError("OCR returned malformed JSON")`.
2. A JSON object with neither `natural_text` nor `text` raises `ValueError("OCR page had no text")`.
3. Any page whose final text is blank after `strip()` raises `ValueError("OCR page had no text")`.
4. Content that isn't JSON, or JSON that isn't an object, stays as it is.

- [ ] **Step 1: Write the failing tests**

```python
async def test_local_ocr_rejects_malformed_json():
    reply('{"natural_text": "abc')  -> raises, match "^OCR processing error.*malformed JSON"

async def test_local_ocr_rejects_page_without_text():
    2-page pdf; replies [reply("page1"), reply(json.dumps({"foo": 1}))]  -> raises, match "no text"
    replies [reply("page1"), reply("   ")]  -> raises, match "no text"

async def test_local_ocr_renders_off_event_loop(monkeypatch):
    wrap asyncio.to_thread to record calls;  extract_text_local(image_pdf(1)) succeeds
    the recorded function is svc._render_pages
```

Existing `test_local_ocr_rejects_empty_output` must still pass. Its `{"foo": 1}` reply now fails with "OCR page had no text", which its `.*no text` regex accepts.

- [ ] **Step 2: Run them to make sure they fail**

Run: `pytest tests/test_local_ocr.py -v`
Expected: the 3 new tests FAIL, and the 8 old ones pass.

- [ ] **Step 3: Implement `_render_pages` and the reply rules**

Keep the `LOCAL_OCR_MAX_PAGES` check inside `_render_pages`, so it still raises before any HTTP call.

- [ ] **Step 4: Document the OCR settings in `README.md`.** Add `TYPHOON_API_KEY`, `DASHSCOPE_API_KEY`, `OCR_PROVIDER`, `OLLAMA_URL` and `LOCAL_OCR_MODEL` to the `.env` block, with the same values and comment as `env.example`. Then add this line under the block:

> `OCR_PROVIDER=ollama` keeps scanned resumes on this machine. It needs Ollama running, with `LOCAL_OCR_MODEL` installed.

- [ ] **Step 5: Run the tests and make sure they pass**

Run: `pytest tests/test_local_ocr.py -v`, then the offline suite.
Expected: 11 passed in `test_local_ocr.py`, and 0 failures overall.

- [ ] **Step 6: Commit**

```bash
git add app/services/document_extraction_service.py tests/test_local_ocr.py README.md
git commit -m "Reject malformed or empty local OCR pages and render off the event loop"
```

---

## What next beyond this plan (not code, owner decisions)

- **A real-resume evaluation set.** 10–20 consented, hand-checked real scans: phone photos, paper scans, Thai and English. The 2026-11-13 check showed synthetic gains don't transfer (Thai CER 8.51% fine-tuned vs 9.42% base). Retraining is worth it only once this set exists to measure against.
- **The cloud Qwen live run.** Run the two live suites with `DASHSCOPE_API_KEY` set to see whether `qwen3.8-flash` fixes the 7B extraction misses.
- **Thai or translated job labels.** They don't match English criteria today, so those candidates come out undecided. This is a design question, so it needs a brainstorm first.
- **Fine-tune script guards.** Covered by the separate plan `finetune/docs/superpowers/plans/2026-11-13-finetune-guards.md` on `benchmark`.
