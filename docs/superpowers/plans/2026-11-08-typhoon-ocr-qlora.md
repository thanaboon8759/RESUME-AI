# Real Typhoon OCR Fine-Tune Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fake "fine-tune" with a real QLoRA fine-tune of `scb10x/typhoon-ocr-3b` on rendered Thai/English resumes. Serve it locally through Ollama, test it under the existing selection protocol, and promote it only if it really beats the current OCR.

**Architecture:** Training data comes from the existing synthetic resume renderer (`resume-lab/build_corpus_v2.py`), using new identities that never overlap the evaluation corpus. Training runs on the base Hugging Face weights with 4-bit QLoRA on the RTX 4080. The adapter is merged and converted to GGUF with llama.cpp, then registered in Ollama under a new, honest tag. `resume-lab/evaluate_models.py --stage ocr` decides promotion using the gates in `resume-lab/evaluation/SELECTION-PROTOCOL.md`, on a fresh holdout.

**Tech Stack:** Python 3.10+, PyTorch 2.6 + CUDA 12.4, transformers (Qwen2.5-VL classes), peft 0.21, bitsandbytes 0.50, accelerate, llama.cpp (`convert_hf_to_gguf.py`, `llama-quantize`), Ollama 0.34.

**Spec:** No design doc. This plan comes from the 2026-11-08 finding that nothing was ever actually fine-tuned:
- `train_typhoon_qlora.py` saves `torch.randn(16, 16)` as the adapter and reports a hard-coded loss of 0.042.
- `adapters/typhoon_ocr_lora/adapter_model.bin` is 2 KB.
- `export_ollama_gguf.py` and `Modelfile.typhoon_finetuned` only re-tag `scb10x/typhoon-ocr-3b:latest`.
- All three Typhoon tags in Ollama share the weights blob `2c2720a4…`, which `resume-lab/evaluation/SCORECARD.md` already admits.

The protocol to follow is `resume-lab/evaluation/SELECTION-PROTOCOL.md`.

## Global Constraints

- Work in the worktree `finetune/` on the branch `feat/typhoon-ocr-qlora`, which starts from `origin/benchmark`. This branch is separate from PR 3 and the main app.
- Hardware: one RTX 4080 with 16 GB. Training must fit that: 4-bit base, LoRA only, frozen vision tower, gradient checkpointing.
- Never tune on holdout outputs. Freeze prompts, options and candidates before any holdout run (protocol §Holdout and promotion).
- OCR gates, copied from the protocol: complete every sample with no truncation, mean normalized CER ≤ 0.05 overall and ≤ 0.08 per language group, rank by lowest overall CER, and break ties within 0.001 by latency.
- Never call a model "fine-tuned" unless its weights digest differs from the base and its adapter came from a logged training run.
- No cloud services. The only downloads are the base weights and llama.cpp.
- Don't commit model weights, rendered images or `.gguf` files. Commit generators, configs, logs and summaries.

## Before building: what to expect

The current OCR already scores 0.55–0.78% CER on the synthetic holdout (SCORECARD). The training data comes from the same renderer as the test data, so a gain here shows the model learned this template family. It does not show it handles real resumes better. Only real resumes would show that.

This plan builds and measures the real fine-tune honestly. Treat a "win" as synthetic-only unless the owner adds real, consented resumes to a separate test set. That is outside this plan.

## Review Focus

1. **Training identities leaking into evaluation** (same name or same text as `corpus-v2` or the new holdout). Expected: generation fails. Pinned in Task 2, `test_training_identities_disjoint_from_eval`.
2. **The trainer silently "succeeding" without training**, as the current file does. Expected: a missing dependency or GPU raises an error, and no adapter is written. Pinned in Task 1, `test_trainer_has_no_simulation_path`.
3. **The export changing outputs on its own**, through bad conversion, quantization or a wrong chat template. Expected: a base model round-tripped through llama.cpp/Ollama scores the same CER as the current Ollama base, within 0.001. Gated in Task 3.
4. **Prompt tokens leaking into the loss.** Expected: only answer tokens have labels, and the prompt and image tokens are `-100`. Pinned in Task 4, `test_collator_masks_prompt_tokens`.
5. **Thai getting worse while the overall CER improves.** Expected: the per-language gate (≤ 0.08) and a "not worse on the Thai holdout than the incumbent" check, reported in Task 6.

---

### Task 1: Remove the fake fine-tune

**Files:**
- Delete: `adapters/typhoon_ocr_lora/` and `Modelfile.typhoon_finetuned`
- Rewrite: `train_typhoon_qlora.py` (Task 4 fills in the body), `export_ollama_gguf.py` (Task 3)
- Test: `tests/test_finetune_honesty.py`

- [ ] **Step 1: Write the failing test.** It reads the file text and checks that the fake paths are gone.

```python
def test_trainer_has_no_simulation_path():
    src = Path("train_typhoon_qlora.py").read_text(encoding="utf-8")
    assert "randn" not in src and "dry_run" not in src and "0.042" not in src
    assert not Path("adapters/typhoon_ocr_lora/adapter_model.bin").exists()
```

- [ ] **Step 2: Run it.** Command: `python -m pytest tests/test_finetune_honesty.py -q`. Expected: FAIL.

- [ ] **Step 3: Remove the fake code.**
  - Delete the fake adapter folder and the Modelfile.
  - Reduce `train_typhoon_qlora.py` to a stub whose `main()` raises `NotImplementedError("see Task 4")`.
  - Make `export_ollama_gguf.py` raise `NotImplementedError("see Task 3")`.
  - Add one line under "OCR configurations" in `SCORECARD.md`: "The `typhoon-ocr-finetuned` tag is the base model; a real fine-tune is tracked in this plan."

- [ ] **Step 4: Run it again.** Expected: PASS. Then **commit** `chore: remove simulated fine-tune and fake adapter`.

### Task 2: Training set and fresh holdout, disjoint from evaluation

**Files:**
- Create: `resume-lab/build_training_set.py`, reusing `render` and `new_sample` from `build_corpus_v2.py`
- Output (git-ignored): `resume-lab/training/v1/{train,val}/<id>.png` + `.txt`, and `resume-lab/evaluation/corpus-v3/` (the fresh holdout, same layout as `corpus-v2`)
- Commit: `resume-lab/training/v1/manifest.json` and `corpus-v3/manifest.json`, with ids, languages and sha256 of each `.txt`
- Test: `tests/test_training_set.py`

**Interfaces:**
- Produces: `build_training_set(out_dir: Path, n_train: int, n_val: int, seed: int) -> dict` (the manifest), and `build_holdout_v3(out_dir: Path, n: int, seed: int) -> dict`

- [ ] **Step 1: Write the failing tests.**

```python
def test_training_identities_disjoint_from_eval(tmp_path):
    train = build_training_set(tmp_path / "t", n_train=12, n_val=4, seed=7)
    hold = build_holdout_v3(tmp_path / "h", n=9, seed=99)
    eval_names = names_in("resume-lab/evaluation/corpus-v2/manifest.json")
    train_names = {s["name"] for s in train["samples"]}
    assert not train_names & eval_names
    assert not train_names & {s["name"] for s in hold["samples"]}
    assert not {s["text_sha256"] for s in train["samples"]} & text_hashes(hold, "resume-lab/evaluation/corpus-v2")

def test_language_mix_matches_eval(tmp_path):
    train = build_training_set(tmp_path / "t", n_train=30, n_val=6, seed=7)
    langs = Counter(s["language"] for s in train["samples"])
    assert set(langs) == {"en", "th", "bi"} and min(langs.values()) >= 8
```

- [ ] **Step 2: Run them.** Expected: FAIL, because the module doesn't exist yet.

- [ ] **Step 3: Implement.** Generate new identities by seeded random combination of the name, employer and skill pools in `build_corpus_v2.py`, rejecting any name already in `corpus-v2`. Write a PNG and a scanned-look PNG for each identity, plus the reference `.txt`. Real sizes: 240 train, 30 val, and a corpus-v3 holdout of 9 per language (27). Add `resume-lab/training/`, `resume-lab/evaluation/corpus-v3/*.png`, `models/` and `*.gguf` to `.gitignore`. None of them are ignored today.

- [ ] **Step 4: Run the tests, then run the real build.**
  - Command: `python resume-lab/build_training_set.py --train 240 --val 30 --holdout 27`
  - Expected: the tests pass, and the manifests show 240/30/27 with no overlap.
  - **Commit** the generator, tests and manifests.

### Task 3: Export round-trip gate (go/no-go before any training)

**Files:**
- Rewrite: `export_ollama_gguf.py`
- Create: `Modelfile.template`, using the chat template and SYSTEM text of the current `scb10x/typhoon-ocr-3b` (read with `ollama show --modelfile`)

**Interfaces:**
- Produces: `export_to_ollama(hf_dir: Path, tag: str, quant: str = "Q8_0") -> str`, which returns the Ollama digest. It runs:
  1. `convert_hf_to_gguf.py` to build the text model GGUF
  2. the `--mmproj` export for the vision projector
  3. `llama-quantize`
  4. `ollama create <tag>`

- [ ] **Step 1: Set up.** Download `scb10x/typhoon-ocr-3b` from Hugging Face (about 7.5 GB) to `models/typhoon-ocr-3b-hf/`. Clone llama.cpp at a pinned tag, and `pip install gguf`.

- [ ] **Step 2: Export the untouched base.** Run `python export_ollama_gguf.py models/typhoon-ocr-3b-hf typhoon-ocr-roundtrip`.

- [ ] **Step 3: Run the gate.**
  - Command: `python resume-lab/evaluate_models.py --stage ocr --split development --corpus corpus-v2 --run roundtrip-gate --models typhoon-ocr-roundtrip:latest scb10x/typhoon-ocr-3b:latest`
  - Expected: both have 100% success, and their mean CER differs by ≤ 0.001.
  - **If this fails, stop and report to the owner.** Ollama cannot faithfully serve a re-exported Qwen2.5-VL from this toolchain, and Tasks 4–6 would measure a broken export instead of the training. The alternative, serving through transformers, needs an owner decision.

- [ ] **Step 4: Commit** the exporter, the template and `runs/roundtrip-gate/summary.json`.

### Task 4: Real QLoRA training

**Files:**
- Rewrite: `train_typhoon_qlora.py`
- Test: `tests/test_trainer.py`

**Interfaces:**
- Consumes: the Task 2 manifests and image/text pairs.
- Produces:
  - `make_collator(processor, prompt: str) -> Callable[[list[dict]], dict]`
  - `train(base_dir: Path, data_dir: Path, out_dir: Path, epochs: int = 2, lr: float = 1e-4, max_steps: int | None = None) -> Path`, which writes the adapter, `train_log.jsonl` and `config.json`
  - `merge(base_dir: Path, adapter_dir: Path, out_dir: Path) -> Path`

Settings:
- 4-bit NF4 base and bf16 compute
- LoRA r=16, alpha=32, dropout 0.05, on the language model's `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`; the vision tower stays frozen
- `max_pixels = 1280*28*28`
- batch 1, gradient accumulation 8, gradient checkpointing on
- The prompt is the exact OCR prompt that `resume-lab/automatic_scan.py` sends, so training matches serving.

- [ ] **Step 1: Write the failing tests.**

```python
def test_collator_masks_prompt_tokens(tiny_processor, one_sample):
    batch = make_collator(tiny_processor, PROMPT)([one_sample])
    answer_ids = tiny_processor.tokenizer(one_sample["text"])["input_ids"]
    labeled = batch["labels"][0][batch["labels"][0] != -100].tolist()
    assert labeled[:len(answer_ids)] == answer_ids  # only the answer is learned

def test_trainer_has_no_simulation_path():  # Task 1 test, kept
    ...
```

`tiny_processor` is the real Typhoon processor loaded from `models/typhoon-ocr-3b-hf`. Skip the test if that folder is missing.

- [ ] **Step 2: Run them.** Expected: FAIL.

- [ ] **Step 3: Implement** with `Qwen2_5_VLForConditionalGeneration`, `BitsAndBytesConfig`, `peft.LoraConfig` / `get_peft_model` and a plain PyTorch loop or `transformers.Trainer`. Log the loss for each step and the val loss after each epoch to `train_log.jsonl`. Raise errors when CUDA or a dependency is missing. Never fall back to fake output.

- [ ] **Step 4: Smoke test.**
  - Command: `python train_typhoon_qlora.py --max-steps 20 --out runs/smoke`
  - Expected: the loss is finite at every step, the adapter file is larger than 1 MB, and peak VRAM is under 15.5 GB (logged).

- [ ] **Step 5: Full run.**
  - Command: `python train_typhoon_qlora.py --epochs 2 --out runs/qlora-v1`
  - It runs for hours, so start it in the background.
  - Expected: val loss after epoch 2 is lower than after epoch 1. If it rose, keep the epoch-1 adapter and log that choice.

- [ ] **Step 6: Commit** the trainer, tests, `config.json` and `train_log.jsonl`, but not the weights.

### Task 5: Merge, export, and evaluate on development

- [ ] **Step 1: Export.** Run `merge(...)` and then `export_to_ollama(merged, "typhoon-ocr-qlora-v1")` with the same quant as the Task 3 gate. Record the digest. It must differ from `2c2720a4…`.

- [ ] **Step 2: Evaluate on development.**
  - Command: `evaluate_models.py --stage ocr --split development --corpus corpus-v2 --run qlora-v1-dev --models typhoon-ocr-qlora-v1:latest typhoon-ocr-roundtrip:latest typhoon-ocr-finetuned:latest typhoon-fast:latest`
  - Comparing against `typhoon-ocr-roundtrip` separates the training effect from the export effect.

- [ ] **Step 3: Freeze the candidate order** by development CER, following the protocol. Write it to `frozen-candidates-v7.json`, then **commit**.

### Task 6: Fresh holdout, promotion decision, and final review

- [ ] **Step 1: Evaluate the frozen candidates on the new holdout.**
  - Command: `evaluate_models.py --stage ocr --split holdout --corpus corpus-v3 --run qlora-v1-holdout --models <frozen order>`
  - `evaluate_models.py --corpus` needs `corpus-v3` added to its choices, plus a test for that.

- [ ] **Step 2: Decide** per the protocol.
  - **If promoted:** add a `v7` entry to `model-policy.json` with the new digest, and update SCORECARD with the CER table, the Thai holdout CER versus the incumbent, and the synthetic-only caveat.
  - **If not promoted:** record the failed validation in SCORECARD and change no policy. Both outcomes are valid results.

- [ ] **Step 3: End-to-end check.** Run `automatic_scan.py` on 3 scanned PDFs, one per language, under the chosen policy. Expected: success, and no regression against the v6 numbers in SCORECARD "Actual upload-to-profile results".

- [ ] **Step 4: Whole-branch review** by a fresh reviewer. It should check:
  - the training–evaluation separation
  - the export gate
  - the loss masking
  - honest wording, so no "fine-tuned" claim lacks a digest and training log behind it
  
  Then **commit**. Pushing the branch and opening a PR need the owner's OK.

## Not covered

- **Real resumes.** A claim that the fine-tune helps on real-world resumes needs a real, consented test set.
- **Wiring into the main app.** The PR 3 app calls the cloud Typhoon OCR API (`app/services/document_extraction_service.py:91`). Using a local OCR model there is a separate change.
- **PR 3 live Qwen tests.** These stay in `docs/superpowers/plans/2026-11-08-live-qwen-tests.md` on that branch. They can now run against local `qwen2.5:7b` through Ollama, but only as a pipeline check.
