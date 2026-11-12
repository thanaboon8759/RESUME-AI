# Compare and Adopt the Fine-Tuned OCR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the owner compare the current default OCR (`typhoon-ocr-finetuned`, base weights) with the real fine-tune (`typhoon-ocr-qlora-v1-rp1`) on any resume, including their own. Then make the fine-tune the resume-lab default through the policy tool, and give the main Resume AI app a local Ollama OCR option that uses it.

**Architecture:**
- **Part A, comparison:** a CLI that runs both models on the same files and writes a private side-by-side HTML report.
- **Part B, adoption in resume-lab:** extend `manage_policy.py` so OCR can be judged on its own holdout corpus (`corpus-v3`) while extraction keeps `corpus-v2`. Then freeze and promote policy `v7-qlora` with the existing integrity checks.
- **Part C, main app:** add `OCR_PROVIDER=ollama` to `app/services/document_extraction_service.py`. It renders PDF pages with PyMuPDF and sends them to Ollama with the same prompt resume-lab uses. The cloud Typhoon path stays the default.

**Tech Stack:** Python 3.10+, PyMuPDF, httpx, Ollama 0.34, pytest.

**Spec:** No design doc. This plan comes from the owner's request on 2026-11-08: "compare default and fine-tuned one and working forward into project." The evidence it builds on is PR 4 (`resume-lab/evaluation/SCORECARD.md`, v7 section) and `docs/superpowers/plans/2026-11-08-typhoon-ocr-qlora.md`. The owner's approval of this plan counts as sign-off to switch the resume-lab default (Part B) and to accept the export-gate override recorded in PR 4.

## Global Constraints

- **Branches.**
  - Parts A and B: `feat/typhoon-ocr-qlora` (the `finetune/` worktree), so they land in PR 4.
  - Part C: a new branch `feat/local-ocr` from `origin/main`, in the `repo/` checkout. It is independent of PR 3.
- **The owner's resumes are private.** Reports go to `compare-reports/` at the repo root, which is git-ignored. Never commit, upload or print the full text of a user-supplied resume.
- **No change to selection gates or the protocol.** The new policy must pass `manage_policy.py`'s existing checks (engine fingerprint, frozen gates, digests).
- **Main app default unchanged.** With `OCR_PROVIDER` unset or set to `typhoon`, behaviour is the same as today.
- **Offline suites must pass.** Finetune worktree: `python -m pytest tests -q` (20 passed today). Main app: `python -m pytest -q --ignore=tests/test_real_resume_validation.py --ignore=tests/test_screening_scenarios.py`. On `main` today, 5 screening/extraction tests fail without `DASHSCOPE_API_KEY` (PR 3 fixes them), so the bar is no new failures compared with the `main` baseline and every new test passing.

## Review Focus

1. **A multi-page scanned PDF.** Both the comparison report and the main-app local OCR must handle every page in order and join them. Pinned in Task 1 (`test_compare_handles_multipage_pdf`) and Task 4 (`test_local_ocr_joins_pages_in_order`).
2. **Ollama down, or the model missing.** The comparison reports an error per model instead of crashing. The main app raises the same `Exception("OCR processing error: …")` the Typhoon path raises. Pinned in Task 1 (`test_compare_records_model_error`) and Task 4 (`test_local_ocr_error_is_wrapped`).
3. **Output wrapped in `{"natural_text": …}` or truncated** (`done_reason == "length"`). Wrapped output is unwrapped; truncated output is an error, never silently cut text. Pinned in Task 4 (`test_local_ocr_unwraps_and_rejects_truncation`).
4. **Same tested settings everywhere.** Promotion must use exactly the digests that were tested; `manage_policy` already enforces this. Pinned in Task 3 (`test_promote_rejects_digest_mismatch`).
5. **Resume text appearing in logs or the repo.** No full resume text in logs, and the report folder is git-ignored. Pinned in Task 1 (`test_report_dir_is_gitignored`).

---

## Part A: Comparison

### Task 1: `compare_ocr.py`, a side-by-side report on any file

**Files:**
- Create: `resume-lab/compare_ocr.py`
- Test: `tests/test_compare_ocr.py`
- Modify: `.gitignore` (add `/compare-reports/`)

**Interfaces:**
- Consumes: `server.parse_document(filename, data, ocr_model)` and `evaluate_models.cer` from resume-lab.
- Produces:
  - `compare(files: list[Path], models: list[str], references: dict[str, str] | None = None) -> list[dict]`. It returns one row per (file, model): `{file, model, ok, text, seconds, cer (if reference), error}`.
  - `write_report(rows: list[dict], out: Path) -> Path`, which writes HTML: one column per model, word-level differences highlighted with `difflib`, seconds, and CER when a reference `.txt` with the same name exists.
- CLI: `python resume-lab/compare_ocr.py <files…> [--models A B] [--out compare-reports/<stamp>.html]`. The default models are the first OCR model in `model-policy.json` and `typhoon-ocr-qlora-v1-rp1:latest`.

- [ ] **Step 1: Write the failing tests.** Inject a fake `ocr_runner` so no Ollama is needed. `parse_document` already accepts one.

```python
def test_compare_runs_each_model_on_each_file(tmp_path, fake_runner): ...   # 2 files x 2 models = 4 rows
def test_compare_handles_multipage_pdf(tmp_path, fake_runner): ...           # 2-page scanned PDF -> both pages' text, in order
def test_compare_records_model_error(tmp_path): ...                          # runner raises for model B -> row ok=False, error set, model A row ok
def test_cer_only_when_reference_exists(tmp_path, fake_runner): ...          # x.pdf + x.txt -> cer float; y.pdf alone -> cer None
def test_report_dir_is_gitignored():                                         # git check-ignore compare-reports/x.html exits 0
```

- [ ] **Step 2: Run them.** Command: `python -m pytest tests/test_compare_ocr.py -q`. Expected: FAIL, because the module doesn't exist yet.

- [ ] **Step 3: Implement** `compare_ocr.py` and the `.gitignore` line.

- [ ] **Step 4: Run them again.** Same command. Expected: 5 passed, and the whole suite shows 25 passed.

- [ ] **Step 5: Run it for real** on the 3 corpus-v3 scanned PDFs plus `dev_en_02_lead.png`.
  - Command: `python resume-lab/compare_ocr.py resume-lab/evaluation/corpus-v3/hold3_*_0-scan.pdf …`
  - Expected: an HTML report with both columns filled and CER shown.
  - Open it in the browser pane for the owner. The owner can run the same command on their own resumes.

- [ ] **Step 6: Commit** `feat: side-by-side OCR comparison report`.

## Part B: Adopt in resume-lab

### Task 2: Single development OCR run for freezing

`manage_policy freeze` needs one development OCR run that contains every candidate.

- [ ] **Step 1: Run it.** Command (from `resume-lab/`): `python evaluate_models.py --stage ocr --split development --corpus corpus-v2 --run v7-qlora-dev-ocr --models <the 6 models in frozen-candidates-v7.json>`.

- [ ] **Step 2: Check the order.** `freeze_candidates.ordered(summary,'ocr')` must give the same rank 1 as `frozen-candidates-v7.json` (`typhoon-ocr-qlora-v1-rp1`). **If rank 1 differs, stop and report to the owner.** That would mean dev results are unstable, and promotion would be guesswork.

- [ ] **Step 3: Commit the run.**

### Task 3: Separate OCR holdout corpus in `manage_policy.py`, then promote `v7-qlora`

**Files:**
- Modify: `resume-lab/manage_policy.py` (`main()`, around lines 106-155)
- Test: `tests/test_manage_policy.py`

**Interfaces:**
- New argument `--ocr-holdout-corpus` with choices `['corpus-v2', 'corpus-v3']` and default equal to `--corpus`.
- Freeze records `ocr_holdout_corpus` and its manifest sha256 in the frozen record.
- Promote validates the OCR holdout run against that manifest. Extraction holdout keeps using `--corpus`.
- With the default value, behaviour is byte-identical to today.

- [ ] **Step 1: Write the failing tests.** Use fixture runs copied into `tmp_path` and monkeypatched `ROOT`.

```python
def test_default_ocr_holdout_corpus_keeps_v6_behaviour(...): ...   # promoting v6 inputs reproduces model-policy.json except validated_at
def test_ocr_holdout_uses_its_own_manifest(...): ...               # corpus-v3 OCR run accepted; same run rejected if the record names corpus-v2
def test_promote_rejects_digest_mismatch(...): ...                 # holdout run digest != frozen digest -> SystemExit
```

- [ ] **Step 2: Run them.** Expected: FAIL.

- [ ] **Step 3: Implement** the argument and the per-stage manifest choice. Expected: the tests pass, and the full suite passes.

- [ ] **Step 4: Promote for real.**
  - Freeze: `python manage_policy.py freeze --id v7-qlora --corpus corpus-v2 --ocr-holdout-corpus corpus-v3 --extraction grounded-extraction-v6 --ocr v7-qlora-dev-ocr`
  - Then promote: `python manage_policy.py promote --id v7-qlora --corpus corpus-v2 --ocr-holdout-corpus corpus-v3 --extraction fresh-holdout-extraction-v6 --ocr qlora-v1-holdout`
  - Expected: `model-policy.json` has id `v7-qlora`, OCR order rank 1 `typhoon-ocr-qlora-v1-rp1:latest`, and extraction `qwen2.5:7b` unchanged.

- [ ] **Step 5: Restart the app and check it.**
  - Expected: the page says scanning is ready.
  - Uploading `hold3_th_1-scan.pdf` gets processed by OCR model `typhoon-ocr-qlora-v1-rp1`, which shows in Scan diagnostics.

- [ ] **Step 6: Commit** `feat: promote v7-qlora OCR policy`. Update the SCORECARD v7 heading from "awaiting owner sign-off" to "validated".

## Part C: The main Resume AI app

### Task 4: Local Ollama OCR option

**Files** (in `repo/`, branch `feat/local-ocr` from `origin/main`):
- Modify: `app/services/document_extraction_service.py` (add `extract_text_local(file_bytes) -> str`; `extract_document` picks the OCR function by `OCR_PROVIDER`)
- Modify: `env.example` (add `OCR_PROVIDER=typhoon`, `OLLAMA_URL=http://localhost:11434`, `LOCAL_OCR_MODEL=typhoon-ocr-qlora-v1-rp1:latest`)
- Test: `tests/test_local_ocr.py`

**Interfaces:**
- `extract_text_local(file_bytes: bytes) -> str`:
  - Render each PDF page at 144 dpi (the same as corpus scanned PDFs) to PNG.
  - POST to `{OLLAMA_URL}/api/chat` with `stream=false`, options `{"temperature": 0, "num_ctx": 8192, "num_predict": 4096}`, and resume-lab's exact OCR prompt (`resume-lab/server.py:123`).
  - Unwrap `natural_text`/`text`, raise on `done_reason == "length"`, and join pages with `\n`.
  - Wrap every failure as `Exception(f"OCR processing error: {e}")`, matching the Typhoon path.

- [ ] **Step 1: Write the failing tests.** Patch `httpx.AsyncClient.post`.

```python
async def test_local_ocr_joins_pages_in_order(...): ...              # 2-page PDF -> "page1\npage2", 2 POSTs, images present
async def test_local_ocr_unwraps_and_rejects_truncation(...): ...    # '{"natural_text":"x"}' -> "x"; done_reason "length" -> Exception("OCR processing error...")
async def test_local_ocr_error_is_wrapped(...): ...                  # ConnectError -> Exception startswith "OCR processing error"
async def test_provider_switch(monkeypatch): ...                     # OCR_PROVIDER unset -> typhoon fn called; "ollama" -> local fn called
```

- [ ] **Step 2: Run them.** Expected: FAIL.

- [ ] **Step 3: Implement.** Expected: the 4 new tests pass, and the main-app offline suite has no failures beyond the 5 already on `main`.

- [ ] **Step 4: Live check.**
  - Run `extract_document()` on `finetune/resume-lab/evaluation/corpus-v3/hold3_th_1-scan.pdf` with `OCR_PROVIDER=ollama`.
  - Expected: the returned text has CER ≤ 1% against `hold3_th_1.txt`.

- [ ] **Step 5: Commit** `feat: optional local Ollama OCR using the fine-tuned Typhoon model`.

### Task 5: Final review

- [ ] **Step 1: Two fresh reviews.** One reviewer for PR 4's new commits (Parts A and B), one for `feat/local-ocr` (Part C).
- [ ] **Step 2: One fix pass** for critical and important findings.
- [ ] **Step 3: Pushing,** updating PR 4 and opening a PR for `feat/local-ocr` each need the owner's OK.

## Not covered

- Testing on real resumes. Task 1 gives the owner the tool to compare on their own files. Turning their files into a formal labelled test set is a separate step that needs their consent and labels.
- Making local OCR the main app's default. That would also require Ollama on every deployment.
