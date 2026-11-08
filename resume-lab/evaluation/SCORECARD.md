# Automatic model-selection scorecard

Validated policy: **v6**, local synthetic pilot, October 2026. Selected extraction: **qwen2.5:7b**. Selected OCR configuration: **typhoon-ocr-finetuned:latest**, with **typhoon-fast:latest** and **scb10x/typhoon-ocr-3b:latest** as qualified fallbacks. Users upload files without model selection.

## Coverage and evidence

All six installed completion-capable configurations were tested for extraction; all three vision-capable configurations were tested for OCR. All attempts, including failures, remain in `runs/`. No new models or cloud services were used. Exact digests are in `../model-policy.json` and each run's configuration. The original repository's dummy adapter and mock benchmark were not treated as quality evidence.

The original corpus had five development and six holdout identities. That holdout failed extraction promotion and remains unchanged. Source-only corrections for incomplete inherited development labels are retained separately, and historical results were re-scored without rerunning inference. The expanded corpus has eleven development and nine fresh synthetic holdout identities, with text, digital PDF, PNG and scanned PDF variants. Formats are correlated copies, not independent resumes. Development and holdout share generator/layout rules; real-world template generalization is unproven.

## All-model extraction comparison

Comparable corrected development scores from the five-case v3 comparison:

| Installed model | Schema success | Identity exact | Skill F1 | Date exact | Decision |
|---|---:|---:|---:|---:|---|
| deepseek-r1:8b | 20% | 20% | 20% | 0% | Output/schema failures; refined v4 still 20% success |
| llama3.1:8b | 100% | 80% | 96.0% | 89.3% | Refined expanded v5 had 10/11 successes; fails reliability gate |
| qwen2.5:7b | 100% | 100% | 100% | 58.7% | Improved and independently revalidated below |
| scb10x/typhoon-ocr-3b:latest | 60% | 0% | 0% | 0% | Unsuitable for this text extraction schema |
| typhoon-fast:latest | 60% | 0% | 0% | 0% | Unsuitable for this text extraction schema |
| typhoon-ocr-finetuned:latest | 60% | 0% | 0% | 0% | Unsuitable for this text extraction schema |

Source: `corrected-development-scores.json`, original run `improved-extraction-v3`. The vision variants were tested twice as extractors before exclusion; they were not silently omitted. The expanded final source repairs do not remedy other models' invalid/truncated JSON. Only Qwen qualified as an extractor; there is no approved alternate extraction model.

## Improvements and final extraction

Required nested fields, explicit date/degree instructions and atomic skill splitting improved structured extraction. Conservative, logged repairs restore unique source aliases, organization suffixes, printed date ranges and combined degree/major phrases. Regression tests prevent copying another employer's dates, treating numeric achievements as dates, or overwriting conflicting degrees. No hiring inference is produced.

| Measure | Expanded development, 11 cases | Fresh text holdout, 9 cases | Frozen gate |
|---|---:|---:|---:|
| Schema success | 100% | 100% | 100% |
| Identity exactness | 100% | 100% | ≥95% |
| Skill precision / recall / F1 | 100% / 100% / 100% | 100% / 100% / 100% | F1 ≥90% |
| Employment/education exactness | 97.0% | 96.8% | ≥85% |
| Date exactness | 100% | 90.7% | ≥90% |
| Record precision | 100% | 100% | ≥95% |
| Literal source evidence | 100% | 98.0% | ≥95% |
| Mean seconds | 3.18 | 2.07 | Accuracy before speed |

Sources: `runs/grounded-extraction-v6/summary.json` and `runs/fresh-holdout-extraction-v6/summary.json`. The earlier text holdout v4 scored 94.4% identity and 83.3% dates and was **not promoted**. No gates were relaxed. Held-out v6 English date accuracy is 83.3%, Thai 88.9%, bilingual 100%; the aggregate gate passes, but these small groups do not justify language-specific routing or claims of uniformly high date accuracy.

## OCR configurations

> The `typhoon-ocr-finetuned` tag is the base model; a real fine-tune is tracked in `docs/superpowers/plans/2026-11-08-typhoon-ocr-qlora.md`.

Explicit 8192-token context and 4096-token output limits fixed context starvation. The scanner unwraps Typhoon's `natural_text`/`text` JSON and rejects truncated/invalid wrappers. All three configurations completed every expanded development and fresh held-out case.

| OCR configuration | Development CER, 11 | Holdout CER, 9 | Thai holdout CER | Holdout mean seconds | Policy order |
|---|---:|---:|---:|---:|---:|
| typhoon-ocr-finetuned:latest | 0.571% | 0.780% | 1.509% | 3.92 | 1 |
| typhoon-fast:latest | 0.585% | 0.549% | 0.970% | 4.34 | 2 |
| scb10x/typhoon-ocr-3b:latest | 2.178% | 0.997% | 1.643% | 4.49 | 3 |

Sources: `runs/expanded-ocr-v5/summary.json` and `runs/fresh-holdout-ocr-v6/summary.json`. Gates: 100% success, mean CER ≤5%, per-language mean CER ≤8%. First/second configurations tied within the predeclared 0.001 CER tolerance on development; speed broke the tie. The later holdout is not used to reorder candidates. All variants share the base weight blob `2c2720a40fa3732b175fb69bc5ec58f6b11e0267c770a10ae2726ca33c247b39`; “finetuned” is a tag, not evidence of actual fine-tuning.

## Actual upload-to-profile results

All **36/36** requests through the token-protected HTTP endpoint succeeded with automatic selection. OCR routing was checked for every format. These are functional successes, not error-free transcripts.

| Format, 9 each | Identity exact | Skill F1 | Employment/education | Dates | Record precision | Source CER | Mean seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| UTF-8 text | 100% | 100% | 96.8% | 90.7% | 100% | 0% | 2.55 |
| Digital PDF | 100% | 100% | 96.3% | 97.2% | 96.3% | 0% | 2.04 |
| PNG image | **92.6%** | 100% | 87.5% | **84.1%** | **88.9%** | 0.780% | 7.49 |
| Scanned PDF | **92.6%** | 100% | 94.0% | 90.7% | 96.3% | 1.116% | 5.60 |

Source: `upload-verification-v6/summary.json`; each full result is saved in its attempts log. **Image-based identity accuracy and image date/record accuracy are below the component selection thresholds.** Component gates do not certify the full OCR pipeline. Automatic routing is enabled as a reviewable testing tool; names, contacts and dates still require comparison with the original. The app surfaces OCR warnings and source text. These holdout integration results were not used to tune inference.

## Resources and reproducibility

Fresh holdout average prompt/output tokens: Qwen 1166/243; base OCR 4094/128; fast OCR 4126/129; primary OCR 4149/129. Observed post-request VRAM: Qwen 5.98 GiB; base/fast OCR 6.88 GiB. During the primary OCR run, Ollama's resident-model listing reported the shared runner as the fast alias, so no separate exact-name VRAM figure is attributed to the primary. Responses reported the requested primary tag. These are observations, not peak VRAM, energy or monetary costs.

Exact model digests, corpus hashes, server/schema/evaluator/source-repair snapshots, raw replies, token/load counters and failure records are retained. `manage_policy.py promote` verifies frozen protocol/gates and recomputes accuracy from saved outputs using the verified scorer; stale summaries, mismatched corpora and changed digests/configurations are rejected. Runtime policy also pins the engine fingerprint. A test-only changed digest or simulated failure never falls back to an untested model.

Forty unit tests cover parsing, schema failures, source repairs, digest/configuration mismatches, absent primary models, fallback provenance, total failure, offline text preview and promotion integrity. Browser verification is recorded separately in `BROWSER-VERIFICATION.md`. Latencies include local load effects; p95 on nine samples is unstable. CER normalizes Unicode, case and whitespace. Literal matching is not semantic factuality, and achievement recall is not measured. Thai rendering lacks RAQM. See `../README.md` for run commands and parser/security limits.

## v7 candidate: real QLoRA fine-tune (2026-11-08), awaiting owner sign-off

The `typhoon-ocr-finetuned` tag never contained trained weights. `typhoon-ocr-qlora-v1` is a real 4-bit QLoRA fine-tune of `scb10x/typhoon-ocr-3b`:
- **Training:** LoRA r=16, applied to the language model only, for 2 epochs. It used 240 training and 30 validation resumes rendered by `build_training_set.py`, none of whose identities appear in corpus-v2 or corpus-v3. Validation loss fell from 0.0163 to 0.0051. The log is in `runs/qlora-v1-train/`.
- **Weights:** digest `eb51dae6…`, different from the base `2c2720a4…`.
- **Serving variant:** `-rp1` is the same weights with `repeat_penalty 1.0`. It was chosen on development data only and frozen before the holdout run.

| OCR configuration | Dev CER, corpus-v2 (11) | Dev Thai | Holdout CER, corpus-v3 (27) | Holdout Thai | Holdout mean seconds | Frozen rank |
|---|---:|---:|---:|---:|---:|---:|
| typhoon-ocr-qlora-v1-rp1 | 0.327% | 0.366% | 0.087% | 0.260% | 3.79 | 1 |
| typhoon-ocr-finetuned (v6 #1) | 0.571% | 0.782% | 0.229% | 0.402% | 3.59 | 2 |
| typhoon-fast | 0.585% | 0.483% | 0.599% | 1.625% | 3.94 | 3 |
| typhoon-ocr-qlora-v1 (repeat_penalty 1.2) | 0.663% | 1.228% | 0.074% | 0.222% | 1.41 | 4 |
| typhoon-ocr-roundtrip-rp1 (untrained) | 0.672% | 0.544% | 0.265% | 0.622% | 3.94 | 5 |
| typhoon-ocr-roundtrip (untrained) | 1.953% | 2.211% | 0.444% | 0.667% | 1.52 | 6 |

**Where the gain comes from.** On dev, with the same pipeline, the repeat-penalty setting alone took the untrained model from 1.953% to 0.672%. Training then took it from 0.672% to 0.327%. All candidates pass the gates. The protocol promotes rank 1 (`promotion-v7.json`). End to end, 3 of 3 corpus-v3 scanned PDFs gave an exact name and skills.

**Caveats:**
- corpus-v3 and the training data come from the same generator, so the holdout advantage is optimistic.
- corpus-v2, made by a different generator, is the more independent comparison, and the fine-tune also leads there.
- Formats remain correlated copies.
- Nothing here shows a gain on real resumes.
- `model-policy.json` remains v6 until the owner approves.
