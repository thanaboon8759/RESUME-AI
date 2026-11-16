# Benchmark Lab Security and Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove a real person's resume from the public benchmark branch, close the file-read and file-write holes in `web_ui.py`, and fix the remaining errors the 2026-11-16 audit found on `benchmark`.

**Architecture:** The path rules go in a new, light module, `lab_paths.py`. It doesn't depend on torch or OCR libraries, so tests can import it. `web_ui.py` imports torch, PaddleOCR and an embedding model when it loads, so tests never import it. They check its source instead, and test the helpers it uses.

**Tech Stack:** Python 3.12, FastAPI (`web_ui.py`), pytest, pyflakes (dev check).

**Spec:** None written. The 2026-11-16 self-audit results in Context are the spec.

## Context: 2026-11-16 audit (benchmark @ 0c26508)

1. **Real personal data.** A real-resume PDF in `benchmark_data/` (its path is in the git-ignored ledger) is a real person's resume, with a gmail address and a phone number, and isn't marked as a sample. It's been public since 2026-10-01 (commit d608f5a). `web_ui.py:131-132` shows the person's full name on a sample button, and `web_ui.py:389,396` makes it the default sample.
2. **`web_ui.py` lets any website read and write files on the machine.** It binds to 127.0.0.1:8000, but it has `allow_origins=["*"]` (line 51), so any page open in the browser can call it and read the replies:
   - `/api/batch` (line 946) takes any `directory` and returns the extracted text of every document in it.
   - `/api/process` (line 915) joins `sample` onto `benchmark_data/` without a check, so `../` reads any file.
   - It joins the uploaded `file.filename` onto a temp dir, so `../` writes anywhere.
   - When a sample is used, the temp dir is never removed.
3. **Undefined name.** `eval/benchmark.py:54` calls `logger.warning`, but `logger` is never defined. If Ollama is down, that path crashes with NameError.
4. **Deferred minor from the fine-tune review.** `merge()` with a missing or wrong `adapter_dir` fails only after loading the full bf16 base model on CPU, which takes minutes.
5. **Secrets: none found** in this branch's history. The `api_key="ollama"` strings are placeholders.

**Owner actions, not code** (each needs an explicit yes, and is done in Task 4 only after it):
- Purge `the real-resume PDF` from history: rewrite and force-push.
- Contact the person whose resume was published, if the owner knows them.

## Global Constraints

- Work on branch `fix/lab-security`, which branches from `benchmark` at 0c26508.
- Test command: `python -m pytest tests -q`. It has 42 passing tests at the start and must have 0 failures after every task.
- **`web_ui.py` CORS:** `allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"]`, the page's own origins only.
- **Batch directories** must resolve to `benchmark_data/` or a folder inside it. Anything else returns 404.
- **The default sample becomes `english_resume.pdf`.**
- No new runtime dependencies. pyflakes is dev-only.

## Review Focus

1. **The existing samples still load by name.** Run `resolve_sample("english_resume.pdf")` and `resolve_sample("thai_resume.pdf")`. (Task 2 test: `test_known_samples_resolve`.)
2. **Windows-style traversal:** `..\\x`, `C:\\x` and absolute paths are rejected, as `../` is. (Task 2 test: `test_windows_paths_rejected`.)
3. **An upload name with folders keeps only its last part,** so `a/b/cv.pdf` is saved as `cv.pdf` rather than rejected, since browsers can send that. (Task 2 test: `test_upload_name_keeps_basename`.)
4. **The batch default, `"benchmark_data"`, still works.** (Task 2 test: `test_default_batch_dir_allowed`.)
5. **The lab UI still has a default sample after removing the real one,** and no button points at a file that no longer exists. (Task 1 test: `test_ui_samples_exist`.)

---

### Task 1: Remove the real resume (finding 1)

**Files:**
- Delete: the real-resume PDF in `benchmark_data/` (path in the git-ignored ledger)
- Modify: `web_ui.py` (lines 130-133, the sample button; lines 389 and 396, the default sample)
- Test: `tests/test_lab_hygiene.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
def test_real_resume_removed():
    # (rewritten during execution) test_only_approved_samples: benchmark_data holds only allowlisted sample files
    # and web_ui.py names no file outside that list

def test_ui_samples_exist():
    src = Path("web_ui.py").read_text(encoding="utf-8")
    for name in set(re.findall(r"loadSample\('([^']+)'\)", src)):
        assert (Path("benchmark_data") / name).exists(), name
```

- [ ] **Step 2: Run them to make sure they fail.** Run `python -m pytest tests/test_lab_hygiene.py -v`. Expected: `test_real_resume_removed` FAILS, and `test_ui_samples_exist` passes.

- [ ] **Step 3: Delete the PDF and its button, and make `english_resume.pdf` the default sample.**

- [ ] **Step 4: Run the tests and make sure they pass:** `tests/test_lab_hygiene.py`, then the full suite.

- [ ] **Step 5: Commit**

```bash
git rm -q benchmark_data/<real-resume>.pdf   # path in the git-ignored ledger
git add web_ui.py tests/test_lab_hygiene.py
git commit -m "Remove a real person's resume from the benchmark samples"
```

### Task 2: Close the web UI file holes (finding 2)

**Files:**
- Create: `lab_paths.py`
- Modify: `web_ui.py` (line 51 CORS, `/api/process` lines 915-943, `/api/batch` lines 946-950)
- Test: `tests/test_lab_paths.py` (new), `tests/test_lab_hygiene.py`

**Interfaces:**
- Produces `lab_paths.py`, with no heavy imports, containing:
  - `SAMPLES_DIR = Path("benchmark_data")`
  - `resolve_sample(name: str, root: Path = SAMPLES_DIR) -> Path | None`:
    - returns `root / name` only if `name` is a plain file name: no `/` or `\`, not absolute, no drive letter, and not `.` or `..`
    - also requires that the path resolves inside `root` and exists
    - otherwise returns `None`
  - `resolve_batch_dir(directory: str, root: Path = SAMPLES_DIR) -> Path | None`: returns the resolved directory only if it's `root` or inside it, and is a directory. Otherwise `None`.
  - `safe_upload_name(filename: str) -> str`:
    - returns the last path part after splitting on both `/` and `\`
    - raises `ValueError` if that part is empty, `.` or `..`
- How `web_ui.py` uses them:
  - `/api/process`: a `None` sample is 404. A `ValueError` from the upload name is 400. The upload is saved as `Path(temp_dir) / safe_upload_name(file.filename)`. The `finally` block always removes `temp_dir`.
  - `/api/batch`: a `None` directory is 404.
  - CORS uses the Global Constraints origins.

- [ ] **Step 1: Write the failing tests** in `tests/test_lab_paths.py`, using `tmp_path` as `root` with a file `a.pdf` and a folder `sub/` in it:

```python
def test_known_samples_resolve():             resolve_sample("english_resume.pdf") and resolve_sample("thai_resume.pdf") are not None (real SAMPLES_DIR)
def test_sample_traversal_rejected(tmp_path): for n in ["../x.pdf", "sub/../../x", "..", ".", ""]: resolve_sample(n, tmp_path) is None
def test_windows_paths_rejected(tmp_path):    for n in ["..\\x.pdf", "C:\\Windows\\win.ini", "/etc/passwd", "\\\\server\\share"]: resolve_sample(n, tmp_path) is None
def test_missing_sample_is_none(tmp_path):    resolve_sample("nope.pdf", tmp_path) is None;  resolve_sample("a.pdf", tmp_path) == tmp_path / "a.pdf"
def test_default_batch_dir_allowed():         resolve_batch_dir("benchmark_data") is not None
def test_batch_outside_root_rejected(tmp_path): resolve_batch_dir(str(tmp_path.parent), tmp_path) is None; resolve_batch_dir("C:\\", tmp_path) is None; resolve_batch_dir(str(tmp_path / "sub"), tmp_path) is not None
def test_upload_name_keeps_basename():        safe_upload_name("a/b/cv.pdf") == "cv.pdf"; safe_upload_name("..\\..\\cv.pdf") == "cv.pdf"
def test_upload_name_rejects_empty():         for n in ["", "a/", "..", "x/.."]: raises ValueError
```

In `tests/test_lab_hygiene.py`:

```python
def test_web_ui_has_no_open_cors_and_uses_path_rules():
    src = Path("web_ui.py").read_text(encoding="utf-8")
    assert 'allow_origins=["*"]' not in src
    assert "resolve_sample(" in src and "resolve_batch_dir(" in src and "safe_upload_name(" in src
```

- [ ] **Step 2: Run them to make sure they fail.** Run `python -m pytest tests/test_lab_paths.py tests/test_lab_hygiene.py -v`. Expected: ImportError for `lab_paths`, and the source check FAILS.

- [ ] **Step 3: Create `lab_paths.py`, and wire it and the CORS change into `web_ui.py`.**

- [ ] **Step 4: Run the tests and make sure they pass:** both files, then the full suite. Also run `python -m pyflakes web_ui.py lab_paths.py` and expect no `undefined name` lines.

- [ ] **Step 5: Commit**

```bash
git add lab_paths.py web_ui.py tests/test_lab_paths.py tests/test_lab_hygiene.py
git commit -m "Stop the web UI reading or writing files outside benchmark_data"
```

### Task 3: Fix undefined names and fail fast in merge (findings 3, 4)

**Files:**
- Modify: `eval/benchmark.py` (add a module logger), `train_typhoon_qlora.py` (`merge`)
- Test: `tests/test_lab_hygiene.py`, `tests/test_trainer_guards.py`

**Interfaces:**
- `eval/benchmark.py` gets `logger = logging.getLogger(__name__)` at module level.
- In `merge()`, right after `_check_merge_out`: raise `ValueError(f"{adapter_dir} has no adapter_config.json; pass the adapter folder that training saved")` when `(Path(adapter_dir) / "adapter_config.json")` doesn't exist. This happens before any `from_pretrained` call.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lab_hygiene.py
def test_no_undefined_names():
    files = git ls-files "*.py", excluding "resume-lab/evaluation/runs/" (frozen historical copies)
    out = subprocess.run([sys.executable, "-m", "pyflakes", *files], capture_output=True, text=True).stdout
    assert [l for l in out.splitlines() if "undefined name" in l] == []

# tests/test_trainer_guards.py
def test_merge_refuses_missing_adapter(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "_check_merge_out", lambda b, o: None)
    with pytest.raises(ValueError, match="adapter_config.json"):
        t.merge(base_dir=tmp_path / "base", adapter_dir=tmp_path / "nope", out_dir=tmp_path / "out")
```

Add `pyflakes` to the dev requirements this branch uses. If there's no dev list, note in the ledger how to install it.

- [ ] **Step 2: Run them to make sure they fail.** Expected: `test_no_undefined_names` FAILS on `eval/benchmark.py:54`. `test_merge_refuses_missing_adapter` FAILS, either trying to load the model or with an OSError from `from_pretrained`.

- [ ] **Step 3: Add the logger and the adapter check.**

- [ ] **Step 4: Run the tests and make sure they pass:** the two test files, then `python -m pytest tests -q`.

- [ ] **Step 5: Commit**

```bash
git add eval/benchmark.py train_typhoon_qlora.py tests
git commit -m "Define the benchmark logger; fail fast on a missing adapter"
```

### Task 4: Owner-approved actions (STOP: ask first, one yes per action)

- [ ] **Purge the real resume and the person's name from history.** Only after this branch is merged.
  - First run `git branch -r --contains d608f5a` to list every branch that contains the PDF, and show that list to the owner.
  - Deleting the PDF isn't enough. The name is also in commit d608f5a's message and in the `web_ui.py` sample-button text, in every commit up to 0c26508.
  - On a fresh mirror clone, run `git filter-repo --invert-paths --path <pdf path> --replace-text <file> --replace-message <file>`. The file maps the name tokens and the PDF's file name to neutral text. The exact strings are in the git-ignored ledger. Keep the file outside the repo, and delete it afterwards.
  - Then force-push each listed branch.
  - Tell the owner before the push: forks, PR diffs and GitHub's cached views keep the old content. GitHub Support can purge cached views. Every clone must re-clone.
- [ ] **Tell the owner the person's resume was public from 2026-10-01 until the purge.** Whether to contact them is the owner's call.
