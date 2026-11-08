# Scoring Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the three findings from the review of PR 3: negative job weights, fallback reasons shown as "met", and duplicate criterion labels.

**Architecture:** Three small, independent fixes on the existing branch `feat/job-rules-scoring`, so they land in PR 3. The schema rejects bad weights at the API. The fallback criteria become `unknown`. `evaluate` collapses repeated labels to their worst status before it scores.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic 2.13, pytest + pytest-asyncio (`asyncio_mode = auto`), httpx `ASGITransport` for API tests.

**Spec:** No design doc. This plan implements findings 1-3 of the 2026-11-08 review of PR 3. The plan it builds on is `docs/superpowers/plans/2026-11-08-job-rules-scoring.md`, and its decision rules still apply.

## Global Constraints

- Work on the branch `feat/job-rules-scoring`. Do not create a new branch.
- Do not change the stored `Candidate` / `Criterion` JSON shape.
- No new dependencies.
- Tests must pass without a real `DASHSCOPE_API_KEY`.
- Offline suite command: `python -m pytest -q --ignore=tests/test_real_resume_validation.py --ignore=tests/test_screening_scenarios.py`. It currently reports 61 passed.

## Review Focus

1. **Existing job rows with a negative weight.** `Job` is also the `response_model` for `GET /api/jobs/`, so a stored bad row would make listing jobs return 500. The seed data has none (`seed_db.py:84`, all positive), and before this branch weights had no effect. Accepted; mention it in the PR. No test.
2. **A weight of exactly 0 must stay allowed** (`ge=0`, not `gt=0`). Pinned in Task 1, `test_create_job_accepts_zero_weight`.
3. **Status ranking for duplicates.** The order is unmet worst, then partial, unknown, met. Rejecting comes before "not sure". Pinned in Task 3, `test_duplicate_labels_keep_worst_status`.
4. **Duplicates that differ only in case or spacing** (`"Python"` and `" python"`) count as the same item. Pinned in Task 3, same test.
5. **A duplicate must count toward the score only once.** Pinned in Task 3, `test_duplicate_labels_score_once`.

---

### Task 1: Reject negative job weights at the API

**Files:**
- Modify: `app/schemas/job.py:10`
- Test: `tests/test_jobs.py`, reusing that file's `AsyncClient(transport=ASGITransport(app=app))` pattern and its `job_service` monkeypatch

**Interfaces:**
- Produces: `Job.weights: Dict[str, conint(ge=0)]`

- [ ] **Step 1: Write the failing tests.** Add them to `tests/test_jobs.py`. `job_service.create_job` is monkeypatched to return `job.id`, as in `test_create_job`.

```python
async def test_create_job_rejects_negative_weight(monkeypatch):
    # POST /api/jobs/ with a valid body except weights={"Python": -1}
    assert response.status_code == 422

async def test_create_job_accepts_zero_weight(monkeypatch):
    # same body with weights={"Python": 0}
    assert response.status_code == 200
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_jobs.py -q`
Expected: `test_create_job_rejects_negative_weight` fails because the status is 200, not 422. The zero-weight test already passes.

- [ ] **Step 3: Implement.** In `app/schemas/job.py`, change the field to `weights: Dict[str, conint(ge=0)]`, with `conint` imported from `pydantic`.

- [ ] **Step 4: Run them to verify they pass**

Run: `python -m pytest tests/test_jobs.py -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/schemas/job.py tests/test_jobs.py
git commit -m "fix: reject negative job weights"
```

### Task 2: Mark fallback reasons as unknown, not met

**Files:**
- Modify: `app/services/candidate_service.py:137-147`
- Test: `tests/test_candidate_service.py`

- [ ] **Step 1: Write the failing test.** Patch everything the same way as `test_create_candidate_unknown_job`.

```python
async def test_fallback_reasons_are_unknown():
    # ScreeningResult(score=61, decision=shortlisted, criteria=[], reasons=["Lacks SQL"]); get_job returns None
    cand = await create_candidate(...)
    assert [x.status for x in cand.criteria] == [CriterionStatusEnum.unknown]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_candidate_service.py -q`
Expected: FAIL, because the status is `met`

- [ ] **Step 3: Implement.** In the legacy fallback block, set `"status": CriterionStatusEnum.unknown`, and update the block's comment to say why: these reasons were never checked against the job.

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m pytest tests/test_candidate_service.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add app/services/candidate_service.py tests/test_candidate_service.py
git commit -m "fix: show unchecked fallback reasons as unknown, not met"
```

### Task 3: Collapse duplicate criterion labels to the worst status

**Files:**
- Modify: `app/services/scoring.py`, inside `evaluate`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: `evaluate(criteria, job, ai_score) -> Outcome`, `_norm`, `_find`, all already in `scoring.py`
- Produces: no new public names. `evaluate` keeps its signature.

- [ ] **Step 1: Write the failing tests** in `tests/test_scoring.py`, using its `job()` and `c()` helpers.

```python
def test_duplicate_labels_keep_worst_status():
    out = evaluate([c("Python", "met"), c(" python", "unmet")], job(mandatory=["Python"]), ai_score=90)
    assert out.has_blocker and out.decision == DecisionEnum.rejected

def test_duplicate_labels_score_once():
    out = evaluate([c("A", "met"), c("a", "met"), c("B", "unmet")], job(), ai_score=0)
    assert out.score == 50
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_scoring.py -q`
Expected: 2 failed. The first is not blocked, and the second scores 67.

- [ ] **Step 3: Implement.** At the start of `evaluate`, collapse `criteria` by `_norm(label)`, keeping the first label's text and the worst status. Rank: `unmet` 0, `partial` 1, `unknown` 2, `met` 3, lowest wins. Score and look up mandatory items from the collapsed list. A private `_WORST_FIRST` order constant is enough. Do not add a public function.

- [ ] **Step 4: Run them to verify they pass**

Run: `python -m pytest tests/test_scoring.py -q`
Expected: `13 passed`

- [ ] **Step 5: Run the offline suite, then commit**

Run: `python -m pytest -q --ignore=tests/test_real_resume_validation.py --ignore=tests/test_screening_scenarios.py`
Expected: `66 passed`

```bash
git add app/services/scoring.py tests/test_scoring.py
git commit -m "fix: duplicate AI criteria count once with their worst status"
```

## Not covered

- Candidate rows that were already saved keep their old "met" fallback statuses. There is no backfill.
- Pushing and updating the PR description (add Review Focus 1) happens after the final review, and needs the owner's OK.
