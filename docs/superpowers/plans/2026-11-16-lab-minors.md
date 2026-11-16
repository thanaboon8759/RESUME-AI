# Lab Leftover Minors (benchmark) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the items left on `benchmark` after the 2026-11-16 purge: bad upload names cause a 500, the pyflakes test can pass with no pyflakes, local run logs are committable, and one sample PDF has no recorded source.

**Architecture:** Tighten `lab_paths.safe_upload_name` (the one place upload names are checked), harden one test, add ignore rules and a sources note.

**Tech Stack:** Python 3, FastAPI, pytest, pyflakes, PyMuPDF.

**Spec:** the "deferred minors" list from the 2026-11-16 session.

## Global Constraints

- Branch `fix/lab-minors` off `benchmark` (1362a67). One PR.
- `safe_upload_name` keeps its signature `safe_upload_name(filename: str) -> str` and raises `ValueError` for anything it refuses; `web_ui.py` already turns that into a 400.
- Do not commit `merge.log` or `runs-qlora-v1.log`; they stay on disk, ignored.

## Review Focus

1. Upload name with a NUL byte (`"cv\x00.pdf"`) → 400 "Invalid file name", not 500 (Task 1).
2. Windows-reserved names (`CON.pdf`, `nul.txt`, `COM1`) → refused, since opening them hits a device (Task 1).
3. Name longer than 200 characters → refused, not an OSError 500 (Task 1).
4. Names with `<>:"|?*` or a trailing dot/space → refused (Task 1).
5. Normal names with spaces, Thai letters or several dots (`ประวัติ v2.final.pdf`) → still accepted unchanged (Task 1).

---

### Task 1: Upload names that the OS cannot open are a 400

**Files:**
- Modify: `lab_paths.py:safe_upload_name`
- Test: `tests/test_lab_paths.py`

- [ ] **Step 1: Write the failing tests**
```python
def test_upload_name_rejects_unopenable():
    for name in ["cv\x00.pdf", "a\x1fb.pdf", "CON.pdf", "nul.txt", "COM1", "a<b.pdf", 'a"b.pdf',
                 "a|b.pdf", "a?.pdf", "a*.pdf", "cv.pdf.", "cv.pdf ", "x" * 201 + ".pdf"]:
        with pytest.raises(ValueError):
            safe_upload_name(name)

def test_upload_name_keeps_normal_names():
    for name in ["my cv.pdf", "ประวัติ v2.final.pdf", "a-b_c (1).docx", "console.pdf"]:
        assert safe_upload_name(name) == name
```

- [ ] **Step 2: Run** `python -m pytest tests/test_lab_paths.py -q` — Expected: `test_upload_name_rejects_unopenable` FAILS.

- [ ] **Step 3: Implement** in `safe_upload_name`, after taking the basename and stripping the drive: raise `ValueError` if the name matches `[\x00-\x1f<>:"|?*]`, ends in `.` or space, is over 200 characters, or its stem before the first dot, uppercased, is in `{"CON","PRN","AUX","NUL","COM1".."COM9","LPT1".."LPT9"}`.

- [ ] **Step 4: Run** `python -m pytest -q` — Expected: all pass. Then start `web_ui.py` and POST a file named `cv\x00.pdf` to `/api/process` with `Origin: http://127.0.0.1:8000`; expected status 400.

- [ ] **Step 5: Commit** `git commit -am "fix(lab): refuse upload names the OS cannot open (was a 500)"`

### Task 2: Lint test fails without pyflakes; dev requirements list it

**Files:**
- Modify: `tests/test_lab_hygiene.py:test_no_undefined_names`
- Create: `requirements-dev.txt` (`pytest`, `pyflakes`)

- [ ] **Step 1: Change the test**: first line `import pyflakes  # noqa: F401  (missing tool must fail, not pass empty)`; also assert the pyflakes run's stderr has no `No module named`.

- [ ] **Step 2: Verify RED** in a throwaway venv without pyflakes: `python -m venv %TEMP%\nopf && %TEMP%\nopf\Scripts\python -m pip install pytest -q && %TEMP%\nopf\Scripts\python -m pytest tests/test_lab_hygiene.py::test_no_undefined_names -q` — Expected: FAIL (ModuleNotFoundError). Delete the venv after.

- [ ] **Step 3: Create** `requirements-dev.txt` with `pytest` and `pyflakes`, one per line.

- [ ] **Step 4: Run** `python -m pytest -q` in the normal env — Expected: all pass.

- [ ] **Step 5: Commit** `git commit -am "test(lab): pyflakes check cannot pass without pyflakes"`

### Task 3: Run logs are ignored; sample sources are recorded

**Files:**
- Modify: `.gitignore` (add `*.log` under "Temporary / OS")
- Create: `benchmark_data/SOURCES.md`
- Modify: `benchmark_data/real_functional_resume.pdf` (clear the PDF metadata author/title only)
- Test: `tests/test_lab_hygiene.py` (`test_run_logs_are_ignored`, `test_every_sample_has_a_source`, `test_sample_pdfs_have_no_author`)

- [ ] **Step 1: Write the failing tests**
```python
def test_run_logs_are_ignored():
    import subprocess
    assert subprocess.run(["git", "check-ignore", "-q", "runs-qlora-v1.log"], cwd=ROOT).returncode == 0

def test_every_sample_has_a_source():
    text = (ROOT / "benchmark_data" / "SOURCES.md").read_text(encoding="utf-8")
    assert all(f"`{name}`" in text for name in APPROVED_SAMPLES)

def test_sample_pdfs_have_no_author():
    import fitz
    for p in (ROOT / "benchmark_data").glob("*.pdf"):
        assert not fitz.open(p).metadata.get("author"), p.name
```

- [ ] **Step 2: Run** `python -m pytest tests/test_lab_hygiene.py -q` — Expected: the three new tests FAIL.

- [ ] **Step 3: Implement**: add `*.log` to `.gitignore`. Write `SOURCES.md` as a table, one row per file in `APPROVED_SAMPLES`: `real_functional_resume.pdf` = public US university career-centre "Functional Resume Sample" (fictional person, 2004); the other four = synthetic, generated for this project. Clear metadata with `doc.set_metadata({})` then `doc.save(tmp, garbage=4)` and replace the file; page text must be unchanged (compare `get_text()` before/after in the step).

- [ ] **Step 4: Run** `python -m pytest -q` — Expected: all pass. `git status` must not list either `.log` file.

- [ ] **Step 5: Commit** `git add .gitignore benchmark_data tests && git commit -m "chore(lab): ignore run logs, record sample sources, clear PDF author"`
