# Leftover Minors (main) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the four small items left on `main` after the 2026-11-16 purge: identifying prose in the sample resume, a weak structure test, unchecked `tests/` lint, and a path to make the `uploads` bucket private on older Supabase projects.

**Architecture:** Test-and-fixture changes plus one standalone SQL file. No app code changes except what pyflakes forces.

**Tech Stack:** Python 3, pytest, pyflakes, Supabase Postgres.

**Spec:** the "deferred minors" list from the 2026-11-16 session (this plan restates each one).

## Global Constraints

- Branch `fix/leftover-minors` off `main` (ed57a14). One PR.
- No real names, schools, companies, emails or phones in any committed file. Placeholders use the word `Example` (e.g. `Example University`).
- Never print the replaced real strings in commit messages, test names or PR text.
- Full suite stays green: `python -m pytest -q` (live Qwen tests skip without a key).

## Review Focus

1. A future edit adds a real organisation name back into a test resume → hygiene test fails (Task 1 test).
2. A block marker is dropped or duplicated while editing `SAMPLE_RESUME` → structure test fails (Task 1 test).
3. pyflakes not installed in the environment → the lint test errors instead of passing empty (Task 2 test).
4. Running the bucket SQL twice, or on a project without the bucket → no error, no change (Task 3: `UPDATE … WHERE`, idempotent).
5. A monkeypatch target renamed in app code → test errors immediately (Task 2, `raising=False` removed).

---

### Task 1: Synthetic sample resume has no identifying organisations; structure test is strict

**Files:**
- Modify: `tests/test_real_resume_validation.py` (the `SAMPLE_RESUME` literal, lines ~54-160)
- Modify: `tests/test_repo_hygiene.py` (`test_replacement_keeps_structure`, add `test_test_resumes_use_example_orgs`)

- [ ] **Step 1: Write the failing tests** in `tests/test_repo_hygiene.py`

```python
ORG_WORD = re.compile(r"[^\n]*\b(University|College|School|Institute|Co\.,? ?Ltd|Company)\b[^\n]*")

def test_test_resumes_use_example_orgs():
    from tests.test_real_resume_validation import SAMPLE_RESUME
    bad = [m.group(0) for m in ORG_WORD.finditer(SAMPLE_RESUME) if "Example" not in m.group(0)]
    assert not bad, f"{len(bad)} line(s) name a real organisation"  # count only: CI logs must not echo names
```

Replace `test_replacement_keeps_structure` body with:
```python
    ids = re.findall(r"\[ID: b(\d+)\]", SAMPLE_RESUME)
    assert ids == [str(i) for i in range(len(ids))] and len(ids) >= 20  # b0..bN, in order, no gaps
    assert all(k.split()[0] in SAMPLE_RESUME.lower() for k in PROJECT_KEYWORDS)
    assert "narin.example@example.com" in SAMPLE_RESUME
```

- [ ] **Step 2: Run** `python -m pytest tests/test_repo_hygiene.py -q` — Expected: `test_test_resumes_use_example_orgs` FAILS (count ≥ 1).

- [ ] **Step 3: Edit `SAMPLE_RESUME`**: replace every real university, school, company or place name with `Example University` / `Example Company` / `Example City`. Keep block IDs, line wrapping, project titles and skill words unchanged so `PROJECT_KEYWORDS` and live evidence tests still match.

- [ ] **Step 4: Run** `python -m pytest -q` — Expected: all pass.

- [ ] **Step 5: Commit** `git commit -am "test: sample resume uses example organisations; strict block-id check"`

### Task 2: pyflakes covers tests/ and cannot pass silently; no `raising=False` on real targets

**Files:**
- Modify: `tests/test_repo_hygiene.py:test_pyflakes_clean`
- Modify: `tests/test_document_extraction.py`, `tests/test_evidence_helpers.py`, `tests/test_real_resume_validation.py`, `tests/test_resume_extraction.py`, `tests/test_screening.py` (unused imports, placeholder-less f-strings)
- Modify: `tests/test_decisions.py:28`, `tests/test_job_ownership.py:28`, `tests/test_uploads_api.py:36,91` (drop `raising=False`)

- [ ] **Step 1: Change the test**: add `import pyflakes  # noqa: F401  (missing tool must fail, not pass empty)` at the top of `test_pyflakes_clean`, add `"tests"` to the checked paths, and also assert `out.returncode == 0`.

- [ ] **Step 2: Run** `python -m pytest tests/test_repo_hygiene.py::test_pyflakes_clean -q` — Expected: FAIL listing the ~10 test-file warnings.

- [ ] **Step 3: Fix each warning** (delete unused imports; turn `f"..."` without placeholders into `"..."`). Remove `raising=False` from the four `monkeypatch.setattr` calls above; keep it on `delenv` calls.

- [ ] **Step 4: Run** `python -m pytest -q` — Expected: all pass.

- [ ] **Step 5: Commit** `git commit -am "test: lint tests/ too, fail when pyflakes is missing, strict monkeypatch targets"`

### Task 3: SQL to make the uploads bucket private on existing projects

**Files:**
- Create: `app/database/migrations/2026-11-16-private-uploads-bucket.sql`
- Modify: `README.md` (one line under the database setup section pointing at the file)
- Test: `tests/test_repo_hygiene.py` (`test_bucket_fix_sql_is_private`)

- [ ] **Step 1: Write the failing test**
```python
def test_bucket_fix_sql_is_private():
    sql = (ROOT / "app/database/migrations/2026-11-16-private-uploads-bucket.sql").read_text(encoding="utf-8").lower()
    assert "update storage.buckets" in sql and "public = false" in sql and "where id = 'uploads'" in sql
```

- [ ] **Step 2: Run** it — Expected: FAIL, file not found.

- [ ] **Step 3: Create the file**: a one-line comment (for projects created before 2026-11-16, run once in the Supabase SQL editor) and
`UPDATE storage.buckets SET public = false, file_size_limit = 20971520 WHERE id = 'uploads';`

- [ ] **Step 4: Run** `python -m pytest -q` — Expected: all pass. Also confirm, read-only, through the Supabase connector that `select public from storage.buckets where id='uploads'` on project `dtifvtylpeyercmymtry` returns `false` (it was created private, so the UPDATE is not needed there).

- [ ] **Step 5: Commit** `git commit -am "db: SQL to make the uploads bucket private on older projects"`
