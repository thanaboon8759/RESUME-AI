# Fine-tune Script Guards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `train_typhoon_qlora.py` refuse three inputs that today silently produce a wrong model or destroy files.

**Architecture:** Add guard checks at the top of `train()` and `merge()`, before CUDA or any model loads, so plain CPU tests can check them. No behaviour changes on valid input.

**Tech Stack:** Python 3.12, pytest. torch, transformers and peft are only imported inside the guarded functions, after the guards run.

**Spec:** The deferred minors in `docs/superpowers/plans/2026-11-08-typhoon-ocr-qlora.ledger.md`.

## Context: defects in `train_typhoon_qlora.py` (benchmark 4c2e400)

1. **An empty split trains nothing.** An empty `train` split skips the loop and still saves an adapter that has never been trained (line 139). An empty `val` split makes `_val_loss` average over nothing.
2. **`merge()` can delete files.** After saving, it deletes every non-`.safetensors` file in `out_dir` (lines 161-163). Pointing `--out` at the base model directory, or at any folder that has other files, deletes them.
3. **Re-runs mix logs.** `train()` opens `train_log.jsonl` in append mode (line 109). A second run into the same `--out` mixes two runs' logs and overwrites `config.json` and the epoch adapters underneath.

## Global Constraints

- Work on branch `fix/finetune-guards`, which branches from `benchmark` at 4c2e400.
- Every guard raises before `_require_cuda()`, `_load_quantized()` or `from_pretrained`.
- Guard errors are `ValueError`, and each message names the offending path or split.
- Test command: `python -m pytest tests -q`. It has 32 passing tests at the start and must have 0 failures at the end.

## Review Focus

1. **A fresh, non-existent `--out` must still work** for both `train()` and `merge()`. (Tests: `test_train_guard_accepts_new_dir`, `test_merge_guard_accepts_new_dir`.)
2. **An existing but empty `--out` directory is allowed,** since people often create it first. (Test: `test_merge_guard_accepts_empty_dir`.)
3. **`--out` given as a different spelling of the base path** (relative vs absolute, trailing slash) must still be refused. Compare `Path.resolve()` values. (Test: `test_merge_refuses_base_dir`.)
4. The merge guard must also refuse a non-empty `out_dir` when `adapter_dir` is valid, so it doesn't matter which argument is wrong. This is covered by `test_merge_refuses_nonempty_dir`.
5. None others found: the script is offline and single-user.

---

### Task 1: Guard `train()` and `merge()` inputs

**Files:**
- Modify: `train_typhoon_qlora.py` (`train` lines 93-109, `merge` lines 150-156)
- Test: `tests/test_trainer_guards.py` (new). Don't add it to `tests/test_trainer.py`, which skips entirely without base weights.

**Interfaces:**
- Produces: `_check_train_inputs(out_dir: Path, train_set: list, val_set: list) -> None`, which raises `ValueError` when:
  - `train_set` is empty: "no training samples in split 'train'"
  - `val_set` is empty: "no validation samples in split 'val'"
  - `out_dir / 'train_log.jsonl'` exists: "<out_dir> already holds a training run; choose a new --out"
- Produces: `_check_merge_out(base_dir: Path, out_dir: Path) -> None`, which raises `ValueError` when:
  - `out_dir` resolves to `base_dir`: "--out must not be the base model directory"
  - `out_dir` exists and has any entries: "<out_dir> is not empty; merge deletes non-weight files there"
- `train()` loads the splits, then calls `_check_train_inputs` **before** `_require_cuda()`, so the split loading moves above it. It then opens the log with `'w'`.
- `merge()` calls `_check_merge_out` as its first line.

- [ ] **Step 1: Write the failing tests** in `tests/test_trainer_guards.py`, using `tmp_path`:

```python
def test_train_refuses_empty_train_split(tmp_path):
    with pytest.raises(ValueError, match="split 'train'"):
        _check_train_inputs(tmp_path / "run", [], [{"x": 1}])

def test_train_refuses_empty_val_split(tmp_path):        same, val empty -> match "split 'val'"

def test_train_refuses_reused_out(tmp_path):
    (tmp_path / "train_log.jsonl").write_text("{}\n")
    -> raises ValueError, match "already holds a training run"

def test_train_guard_accepts_new_dir(tmp_path):          non-empty sets, tmp_path / "new" -> returns None

def test_merge_refuses_base_dir(tmp_path):
    base = tmp_path / "base"; base.mkdir(); (base / "config.json").write_text("{}")
    -> _check_merge_out(base, Path(str(base) + "/")) raises, match "base model directory"
    -> _check_merge_out(base, base / ".." / "base") raises, match "base model directory"

def test_merge_refuses_nonempty_dir(tmp_path):           out has "keep.txt" -> raises, match "not empty"; keep.txt still exists

def test_merge_guard_accepts_new_dir(tmp_path):          out not created -> None
def test_merge_guard_accepts_empty_dir(tmp_path):        out created empty -> None

def test_train_checks_before_cuda(tmp_path, monkeypatch):
    monkeypatch `train_typhoon_qlora.load_samples` to return [] and `_require_cuda` to raise AssertionError("cuda touched")
    train(out_dir=tmp_path / "run") raises ValueError, not AssertionError
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `python -m pytest tests/test_trainer_guards.py -v`
Expected: FAIL with ImportError, because `_check_train_inputs` isn't defined.

- [ ] **Step 3: Implement both guards and wire them in as the Interfaces block says.** Change `open('a'` to `open('w'` on the train log.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `python -m pytest tests/test_trainer_guards.py -v`, then `python -m pytest tests -q`.
Expected: 9 new tests pass, and 41 pass overall with 0 failures.

- [ ] **Step 5: Mark the three items fixed** in `docs/superpowers/plans/2026-11-08-typhoon-ocr-qlora.ledger.md` (lines 24, 25 and 27). Append "fixed on fix/finetune-guards (2026-11-13-finetune-guards.md)" to each. Line 25's other two points stay deferred: sharded-output index handling, and the uncommitted tensor-name check.

- [ ] **Step 6: Commit**

```bash
git add train_typhoon_qlora.py tests/test_trainer_guards.py docs/superpowers/plans/2026-11-08-typhoon-ocr-qlora.ledger.md
git commit -m "Refuse empty splits, reused run dirs and unsafe merge targets"
```

---

**Not in scope:** the resume-lab 8 MB upload cap (`resume-lab/server.py:25`). It rejected an 11.6 MB real Thai scan during the 2026-11-13 check, but `MAX_BYTES` also scales the zip and Ollama-response caps. Raising it is a separate decision, needed only if the lab will handle real scans regularly.
