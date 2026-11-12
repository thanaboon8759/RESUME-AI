# Live Qwen Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the two live Qwen suites check the decision HR actually sees, run them against real Qwen, and update only the expectations the new job rules legitimately changed, before PR 3 is merged.

**Architecture:** The live suites call `screen_candidate_with_qwen` directly and assert on Qwen's raw `decision` and `score`. The app throws those away and recomputes them in `candidate_service` with `scoring.evaluate`, so the suites test a value HR never sees. Task 1 moves the two lines that apply the rules into one shared function. Task 2 makes the live suites use that function and skip cleanly without a key. Task 3 runs them and updates expectations under fixed rules.

**Tech Stack:** Python 3.10+, pytest + pytest-asyncio, DashScope Qwen through the OpenAI SDK, `python-dotenv` (loads `DASHSCOPE_API_KEY` from `.env`, which is git-ignored).

**Spec:** No design doc. This plan comes from the merge note on PR 3 (2026-11-08): "Before you merge, run tests/test_real_resume_validation.py and tests/test_screening_scenarios.py with your Qwen key… Some of their expected results may need updating, since more candidates may now come out 'undecided'." The scoring rules are in `docs/superpowers/plans/2026-11-08-job-rules-scoring.md`.

## Global Constraints

- Work on the branch `feat/job-rules-scoring`, so the changes land in PR 3.
- Never print, log or commit the API key. The key goes only in `.env`, which `.gitignore:5` already ignores.
- Task 3 needs a real `DASHSCOPE_API_KEY`. No key is available in this session's environment, so the owner either adds it to `repo/.env` or runs Task 3 themself.
- Do not loosen Qwen #1 extraction tests or evidence tests (names, emails, projects, the hallucinated-quote checks). Only decision and score expectations may change.
- Offline suite: `python -m pytest -q --ignore=tests/test_real_resume_validation.py --ignore=tests/test_screening_scenarios.py`. It currently reports 70 passed.

## Owner decision expected from Task 3

**Preferred items weigh the same as required ones.** When `job.weights` is empty, every item gets the default weight of 3. The prompt now makes Qwen grade every preferred item too, so a candidate who meets every required item but misses most preferred ones can fall below 70 and come out "undecided".

Case A is the likely example: it has 5 required and 4 preferred items, including AWS, MongoDB and Supabase. If Task 3 shows this, stop and ask the owner:
- **(a)** keep the rule and change the expectation to undecided, or
- **(b)** give preferred items a lower default weight.

Option (b) would be its own small TDD change in `scoring.py`.

## Review Focus

1. **Running bare `pytest` with no key.** Expected: the live tests are skipped, not failed with the built-in mock data. Pinned in Task 2, Step 2.
2. **The pure evidence-helper tests inside `test_real_resume_validation.py`** (`test_fabricated_evidence_rejected`) still run without a key. Pinned in Task 2, Step 2 (the count of non-skipped tests).
3. **Qwen's raw decision and the final decision disagree.** The live tests must assert on the final one. Pinned in Task 1, `test_apply_job_rules_overrides_ai_decision`.
4. **Flaky live output.** One Qwen run can differ from the next. Task 3, Step 2 runs each failing test a second time before any expectation changes.
5. **A Qwen mistake hidden by updating an expectation.** Task 3, Step 3 lets only rule-caused differences change a test.

---

### Task 1: One shared function for applying the job rules

**Files:**
- Modify: `app/services/scoring.py` (add the function at the end)
- Modify: `app/services/candidate_service.py`. Replace the `evaluate(...)` / `model_copy(...)` pair after `screen_candidate_with_qwen`.
- Test: `tests/test_scoring.py`

**Interfaces:**
- Produces: `apply_job_rules(screening: ScreeningResult, job: Job) -> tuple[ScreeningResult, Outcome]`. It returns a copy of `screening` whose `score` and `decision` are replaced by the outcome, together with the outcome itself.

- [ ] **Step 1: Write the failing test**

```python
def test_apply_job_rules_overrides_ai_decision():
    s = ScreeningResult(score=95, decision=DecisionEnum.shortlisted, criteria=[c("Python", "unmet")])
    final, out = apply_job_rules(s, job(mandatory=["Python"]))
    assert final.decision == DecisionEnum.rejected and final.score == 0 and out.has_blocker
    assert s.decision == DecisionEnum.shortlisted  # input not mutated
```

- [ ] **Step 2: Run it.** Command: `python -m pytest tests/test_scoring.py -q`. Expected: collection error, because `apply_job_rules` can't be imported.

- [ ] **Step 3: Implement** `apply_job_rules` in `scoring.py`. Then make `candidate_service.create_candidate` call `screening, outcome = apply_job_rules(screening, job)` in place of its two lines.

- [ ] **Step 4: Run the offline suite.** Expected: `71 passed`. The existing `test_candidate_service.py` tests prove the service still behaves the same.

- [ ] **Step 5: Commit** `refactor: share apply_job_rules between service and tests`

### Task 2: Live suites assert on the final decision and skip without a key

**Files:**
- Modify: `tests/test_real_resume_validation.py` (`get_profile`, `get_result`, around lines 230-245)
- Modify: `tests/test_screening_scenarios.py` (`test_ai_screening_scenario`, around lines 226-240)

**Interfaces:**
- Consumes: `apply_job_rules` from Task 1.

- [ ] **Step 1: Edit both files.**
  - Add `LIVE = os.getenv("DASHSCOPE_API_KEY") not in (None, "", "mock")` after `load_dotenv()`.
  - In `get_profile` and at the top of `test_ai_screening_scenario`, add `if not LIVE: pytest.skip("needs DASHSCOPE_API_KEY")`.
  - In `get_result`, store `apply_job_rules(await screen_candidate_with_qwen(profile, job), job)[0]`.
  - In the scenario test, set `result = apply_job_rules(result, job)[0]` right after screening.
  - Criterion and evidence assertions stay as they are. `apply_job_rules` leaves `criteria` untouched.

- [ ] **Step 2: Verify the skip without a key.** First run `python -m pytest tests/test_real_resume_validation.py tests/test_screening_scenarios.py -q -rs` with `DASHSCOPE_API_KEY` unset. Expected: 0 failed, and every network test is reported as `SKIPPED ... needs DASHSCOPE_API_KEY`. The pure `test_fabricated_evidence_rejected` cases still pass. Then run plain `python -m pytest -q`. Expected: 0 failed. It currently fails without a key, so this is the RED/GREEN check for this task.

- [ ] **Step 3: Commit** `test: live Qwen suites check the final decision and skip without a key`

### Task 3: Run against real Qwen and update rule-caused expectations

Needs the key in `repo/.env`. Never `cat` that file or echo the key.

- [ ] **Step 1: Run both suites.** Command: `python -m pytest tests/test_real_resume_validation.py tests/test_screening_scenarios.py -q -rf > .superpowers/live-run-1.txt 2>&1`, then read the summary at the end of that file. It makes about 15 Qwen calls and may take several minutes, so run it in the background.

- [ ] **Step 2: Re-run only the failures once** with `--lf`. A test that fails only once is flaky. List it in the PR description and don't change it.

- [ ] **Step 3: Sort each consistent failure** into exactly one group:
  - **Rule-caused.** Qwen's criteria statuses are reasonable, and the final decision differs from the old expectation only because of the job rules (for example, undecided from a must-have that is partial or unknown). Update that assertion to the outcome the rules give. If the cause is preferred items lowering the score, stop and ask the owner first (see "Owner decision").
  - **Qwen is wrong.** A criterion status, an extracted fact or an evidence quote is incorrect. Leave the test failing and report it. That is a prompt problem, not a reason to change the test.
  - **Test is wrong.** The assertion contradicts the job it defines. Fix the assertion and say why in the commit message.

- [ ] **Step 4: Rerun until clean.** Run the live suites again, plus the offline suite. Expected: every remaining failure is in the "Qwen is wrong" or flaky list.

- [ ] **Step 5: Commit** `test: update live expectations for job-rule decisions`. Put a table in the commit body: test name, old expectation, new expectation, and the reason for each change.

- [ ] **Step 6: Update the PR 3 description** with the live-run results, and push. Both need the owner's OK.

## Not covered

- Making the prompt more reliable for any "Qwen is wrong" failures. That gets its own plan once we know what fails.
- Running the live tests in CI. The repo has no CI.
