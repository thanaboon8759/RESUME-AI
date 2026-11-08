# Job Rules Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a candidate's score, decision and blocker flag follow the job's own weights and mandatory requirements instead of whatever number Qwen picks, and allow the "undecided" decision.

**Architecture:** Qwen #2 keeps judging each criterion as met / partial / unmet / unknown. A new pure module `app/services/scoring.py` turns those statuses plus the `Job` into the final score, decision and `hasBlocker`. `candidate_service.create_candidate` calls it and overwrites the AI's score and decision before saving. Dead code (`resume_ai_service.py`, `ResumeAIResponse`, `qwen_test.py`) is deleted.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, pytest + pytest-asyncio (`asyncio_mode = auto`), OpenAI SDK against DashScope Qwen.

**Spec:** No design doc exists. This plan implements the issues raised in the session on 2026-11-08: job weights and mandatory items are ignored (every criterion is saved as weight 3, `mandatory: False`, `hasBlocker: False`), and "undecided" is never produced. Rules marked **(planner's call)** below were not confirmed by the project owner. Check them before you start.

## Global Constraints

- Do not change the stored `Candidate` / `Criterion` JSON shape. The frontend reads `full_data` as it is.
- The default weight for a criterion not in `job.weights` is `3`, the value hard-coded today.
- Labels match job items case-insensitively, with surrounding whitespace ignored.
- No new dependencies.
- Tests must pass without a real `DASHSCOPE_API_KEY`. Qwen is always mocked in unit tests.

## Decision rules (planner's call)

Points per status: met = 1.0, partial = 0.5, unmet = 0.0. `unknown` criteria are left out of the score entirely.

- `score = round(100 * Σ(weight × points) / Σ(weight))` over criteria whose status is not unknown. If no criterion is scorable, keep Qwen's score.
- A mandatory item that is **unmet** gives `hasBlocker = True` and `decision = rejected`.
- Otherwise, a mandatory item that is **partial**, **unknown**, or **missing** (no criterion's label matches it) gives `decision = undecided`.
- Otherwise: `score >= 70` → shortlisted, `score < 50` → rejected, anything in between → undecided.

## Review Focus

1. **A mandatory item Qwen never evaluated** (its label is absent from `criteria`). Expected: undecided, not shortlisted. Pinned in Task 1, `test_missing_mandatory_is_undecided`.
2. **Label case or spacing differs from the job** (`"python "` vs `"Python"`). Expected: it still counts as the mandatory, weighted item. Pinned in Task 1, `test_label_matching_ignores_case_and_space`.
3. **Every criterion is unknown, or the list is empty** (for example, a job with no requirements). Expected: no division by zero, and Qwen's score is kept. Pinned in Task 1, `test_no_scorable_criteria_keeps_ai_score`.
4. **A weight of 0 in `job.weights`.** Expected: that criterion has no effect on the score, and an all-zero total does not crash. Pinned in Task 1, `test_zero_weights_do_not_crash`.
5. **The fallback "Unknown Job" with empty requirements** (`candidate_service.py:45`). Expected: candidate creation still succeeds. Pinned in Task 2, `test_create_candidate_unknown_job`.

---

### Task 1: Scoring rules module

**Files:**
- Create: `app/services/scoring.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: `CriterionEvaluation` (`app/schemas/candidate.py`), `Job` (`app/schemas/job.py`), `DecisionEnum`, `CriterionStatusEnum` (`app/schemas/core.py`).
- Produces:
  - `criterion_weight(label: str, job: Job) -> int`
  - `is_mandatory(label: str, job: Job) -> bool`
  - `@dataclass(frozen=True) class Outcome: score: int; decision: DecisionEnum; has_blocker: bool`
  - `evaluate(criteria: list[CriterionEvaluation], job: Job, ai_score: int) -> Outcome`

- [ ] **Step 1: Write the failing tests** in `tests/test_scoring.py`. Use a helper `job(**kw)` that builds a `Job` with empty defaults, and `c(label, status)` that builds a `CriterionEvaluation`.

```python
def test_weighted_score():
    j = job(weights={"Python": 5, "AWS": 1})
    out = evaluate([c("Python", "met"), c("AWS", "unmet")], j, ai_score=10)
    assert out.score == 83          # 5/6
    assert out.decision == DecisionEnum.shortlisted and not out.has_blocker

def test_partial_counts_half_and_default_weight_3():
    out = evaluate([c("Go", "partial"), c("SQL", "met")], job(), ai_score=0)
    assert out.score == 75 and out.decision == DecisionEnum.shortlisted

def test_unmet_mandatory_blocks():
    out = evaluate([c("Python", "unmet"), c("SQL", "met")], job(mandatory=["Python"]), ai_score=99)
    assert out.has_blocker and out.decision == DecisionEnum.rejected

def test_partial_or_unknown_mandatory_is_undecided():
    for s in ("partial", "unknown"):
        out = evaluate([c("Python", s)], job(mandatory=["Python"]), ai_score=99)
        assert out.decision == DecisionEnum.undecided and not out.has_blocker

def test_missing_mandatory_is_undecided():
    out = evaluate([c("SQL", "met")], job(mandatory=["Python"]), ai_score=99)
    assert out.decision == DecisionEnum.undecided

def test_label_matching_ignores_case_and_space():
    j = job(weights={"Python": 5}, mandatory=["Python"])
    assert criterion_weight(" python ", j) == 5 and is_mandatory("PYTHON", j)

def test_thresholds():
    assert evaluate([c("A", "partial")], job(), 0).decision == DecisionEnum.undecided   # 50
    assert evaluate([c("A", "met"), c("B", "unmet"), c("C", "unmet")], job(), 0).decision == DecisionEnum.rejected  # 33

def test_no_scorable_criteria_keeps_ai_score():
    assert evaluate([], job(), ai_score=64).score == 64
    assert evaluate([c("A", "unknown")], job(), ai_score=64).score == 64

def test_zero_weights_do_not_crash():
    out = evaluate([c("A", "met")], job(weights={"A": 0}), ai_score=42)
    assert out.score == 42
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_scoring.py -q`
Expected: collection error, `ModuleNotFoundError: app.services.scoring`

- [ ] **Step 3: Implement `app/services/scoring.py`** as described in "Decision rules". Normalise labels with `.strip().lower()` in one private `_norm` helper. Read the status through `CriterionStatusEnum` so plain strings and enum values both work. When the total weight is 0, treat the criteria as not scorable.

- [ ] **Step 4: Run them to verify they pass**

Run: `python -m pytest tests/test_scoring.py -q`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add app/services/scoring.py tests/test_scoring.py
git commit -m "feat: score and decide candidates from job weights and mandatory rules"
```

### Task 2: Use the rules when creating a candidate, and tell Qwen about them

**Files:**
- Modify: `app/services/candidate_service.py` (criteria mapping around lines 122-145, `Candidate(...)` around 148-170, repository call)
- Modify: `app/services/screening_service.py` (system prompt rules 3, 5 and the schema block)
- Modify: `tests/test_screening.py` (the fixtures must set a fake key)
- Test: `tests/test_candidate_service.py` (new)

**Interfaces:**
- Consumes: `evaluate`, `criterion_weight`, `is_mandatory`, `Outcome` from Task 1.
- Produces: no new names. `create_candidate` keeps its signature.

- [ ] **Step 1: Fix the existing screening tests.** They fail today (2 of 2) because without `DASHSCOPE_API_KEY` the service returns its mock before the patched client is called. In `tests/test_screening.py`, add an autouse fixture: `monkeypatch.setattr("app.services.screening_service.DASHSCOPE_API_KEY", "test-key")`.

Run: `python -m pytest tests/test_screening.py -q`
Expected: `2 passed`

- [ ] **Step 2: Write the failing tests** in `tests/test_candidate_service.py`. Patch `analyze_resume_facts_with_qwen` and `screen_candidate_with_qwen` (as imported in `app.services.candidate_service`) with `AsyncMock`s. Patch `job_repository.get_job` and `candidate_repository.create_candidate`. Call `create_candidate("job1", CandidateCreate(name="Ann Lee", resume_text="..."), "user1")` with no `resume_url`.

```python
async def test_create_candidate_applies_job_rules(...):
    # job: weights={"Python": 5}, mandatory=["Python"]; Qwen says Python unmet, score 90, shortlisted
    cand = await create_candidate(...)
    py = next(x for x in cand.criteria if x.label == "Python")
    assert py.weight == 5 and py.mandatory is True
    assert cand.hasBlocker is True and cand.decision == DecisionEnum.rejected
    saved = create_candidate_mock.call_args.args[3]          # ai_evaluation passed to repository
    assert saved.decision == DecisionEnum.rejected and saved.score == cand.score

async def test_create_candidate_unknown_job(...):
    # get_job returns None; Qwen returns criteria=[] and reasons=["x"], score 61
    cand = await create_candidate(...)
    assert cand.score == 61 and cand.decision == DecisionEnum.undecided
```

- [ ] **Step 3: Run them to verify they fail**

Run: `python -m pytest tests/test_candidate_service.py -q`
Expected: FAIL. The weight is 3, `mandatory` is False, and the decision is shortlisted.

- [ ] **Step 4: Implement the changes in `candidate_service.py`.**
  - Right after `screen_candidate_with_qwen`, call `outcome = evaluate(screening.criteria, job, screening.score)`, then `screening = screening.model_copy(update={"score": outcome.score, "decision": outcome.decision})`.
  - Criteria mapping: `"weight": criterion_weight(crit.label, job)`, `"mandatory": is_mandatory(crit.label, job)`.
  - Pass `hasBlocker=outcome.has_blocker` to `Candidate(...)`.
  - Leave the legacy reasons fallback as it is: weight 3, not mandatory.

- [ ] **Step 5: Update the screening prompt in `screening_service.py`.**
  - Rule 3: evaluate every item in `required`, `preferred` and `mandatory` as its own criterion, and use the item's exact text as `label`.
  - Rule 5: the decision may be `"shortlisted"`, `"rejected"` or `"undecided"`.
  - Schema line: the status is `"met" | "partial" | "unmet" | "unknown"`. Use `unknown` when the profile has no information either way.
  - Change the schema's decision enum to match rule 5.

- [ ] **Step 6: Run the unit suite**

Run: `python -m pytest tests/test_scoring.py tests/test_screening.py tests/test_candidate_service.py tests/test_resume_extraction.py tests/test_main.py -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add app/services/candidate_service.py app/services/screening_service.py tests/test_screening.py tests/test_candidate_service.py
git commit -m "feat: apply job weights, mandatory blockers and undecided to candidate screening"
```

### Task 3: Remove dead code

**Files:**
- Delete: `app/services/resume_ai_service.py`, `qwen_test.py`
- Modify: `app/schemas/candidate.py`. Remove `class ResumeAIResponse`.

- [ ] **Step 1: Confirm nothing references them**

Run: `git grep -n -E "ResumeAIResponse|resume_ai_service|resume_ai_client|document_pipeline import"`
Expected: matches only inside the files being deleted.

- [ ] **Step 2: Delete them, then run the unit suite from Task 2 Step 6.**
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git rm app/services/resume_ai_service.py qwen_test.py
git add app/schemas/candidate.py
git commit -m "chore: remove unused ResumeAI client stub and broken qwen_test script"
```

## Not covered

- `tests/test_real_resume_validation.py` and `tests/test_screening_scenarios.py` call the real Qwen API. Run them by hand with a key after Task 2, since the prompt changed. Their expectations about shortlist or reject may need updating under the new rules.
- `candidate_repository.create_candidate` hard-codes `"position": "Backend Developer"`. This is unrelated and left alone.
