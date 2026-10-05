# Automatic model selection — active implementation

1. Freeze development and independent holdout identities with text, digital PDF, image and scanned-PDF variants. Inspect rendering and record limitations.
2. Inventory exact installed digests, capabilities and shared base weights. Evaluate all completion-capable models for extraction and all vision-capable models for OCR; report incompatible/error cases rather than hiding them.
3. Measure extraction fields, skills, source grounding, Thai dates, OCR CER, schema/failure rates, latency and resource proxies. Preserve raw model replies and per-attempt errors. Failed attempts count toward denominators.
4. Improve development failures, freeze inference configuration, then evaluate holdout once. Do not promote from development-only or mock scores.
5. Write a digest-pinned selection policy, validated fallback order and automatic routes. Make upload-to-readable-result the default; keep actual model provenance in diagnostics.
6. Verify parser limits, unavailable-model/fallback behavior, inference errors and browser upload flows. Publish scorecard, configuration and reproducibility commands.

Current status: initial scanner and all six local models inspected. Existing accuracy reports are development-only and cannot serve as the final gate. No new models or cloud services are needed for the first pass.

## Progress on 4 October 2026

- Frozen 5 development and 6 held-out synthetic identities, each as text, digital PDF, PNG and scanned PDF. Thai development image visually inspected; rendering limitations documented in manifest.
- Completed baseline extraction comparison across all 6 completion-capable installed models: 30 live attempts. Saved original server/evaluator snapshots alongside raw replies. Historical baseline summary uses the older scoring definition and is not a promotion gate.
- Tightened evaluation: extra records and achievement evidence counted; one-to-one organization matching; interrupted-final-record recovery; schema/runtime hashes; per-language summaries; inference time separated from score computation.
- Added required core extraction fields and conservative grouped-skill splitting. Added Pdfium rendering for scanned PDFs using the already-available runtime.
- 19 tests pass, including missing required fields, colon-containing skill names, scanned-PDF rendering, extra records, invented achievements and interrupted logs.
- Revised development extraction and OCR runs launched sequentially. No held-out inference has been performed. No automatic selection policy is promoted yet.

Next: inspect revised development results, fix remaining development failures, freeze the configuration, evaluate held-out cases, and implement/verify the digest-pinned automatic selection policy and default upload flow.

## Development corrections and OCR results

- Completed revised extraction v3 (30 attempts) and baseline OCR v3 (15 attempts). The process handle ended; final summaries prove both completed.
- Corrected OCR context starvation with explicit 8192 context / 4096 output tokens; unwrap `natural_text` as well as `text`; reject truncated JSON and output-limit responses. Improved OCR v4 completed all 15 attempts: mean normalized CER base 3.93%, fast 1.01%, configuration named finetuned 0.92%. These are development scores and the variants share base weights, not evidence of successful training.
- Preserved the original corpus. Added development-only annotation overlay v2 for previously missing job/education labels, full bilingual name, and exact Thai skills. Historical scores were re-derived uniformly from saved responses into corrected-development-scores.json; original reports remain intact. Nested achievements recall is not measured; literal evidence checks predicted achievements only.
- Added fully required nested extraction schema and explicit range/degree/verbatim instructions (resume-facts-v4). Retesting the three general text models in refined-extraction-v4. Vision variants were already tested for text extraction twice and had zero skill F1 on all five development samples; they are excluded from this refinement round, not hidden from the scorecard.
- Added automatic-selection primitives and five tests for changed digests, unknown models, absent primary, validation fallback, empty output and total failure. They are not wired to the upload endpoint until the selected configuration is validated.
- 26 unit tests pass. No held-out inference or policy promotion yet.

## Frozen finalists and held-out run

- Refined extraction v4 complete: Qwen passes all predefined pilot development gates with 5/5 schema successes, identity/skills/dates/record precision/literal evidence 1.0 and employment/education exactness 0.8833. Llama (4/5 successes) and DeepSeek (1/5) fail reliability gates; no alternate extraction model is qualified as fallback.
- Selection protocol and ordered candidates saved before holdout. Common model selection, not unsupported language-specific routing. Qwen extraction; OCR order: configuration named finetuned, fast, base. All OCR variants have shared base weights; names do not imply training quality.
- Model policy primitives now reject malformed/null digests and can bind prompt/schema/inference function fingerprint. Annotation overlay binds the source manifest hash; historical rescoring refuses incompatible corpus hashes.
- 27 tests pass. Held-out extraction and OCR launched sequentially as holdout-extraction-v4 and holdout-ocr-v4. Frozen engine fingerprint: 5492eef4e631fc6aa63b768adce51a26a2577a0c87c1aa3c95142d4f6c71b0b2. Do not modify inference or tune on held-out results.
- Pending: gate held-out results, wire auto selection into upload endpoint and frontend, test actual OCR-to-extraction pipelines and browser uploads, publish final scorecard/policy/limitations. Keep the active goal open.

### Holdout extraction v4 failed promotion

Six of six schema successes, identity 0.9444 (gate 0.95), skill F1 1.0, employment/education 0.9375, dates 0.8333 (gate 0.90), record precision 1.0, literal evidence 0.9632. Do not lower gates or promote this configuration. Preserve the first holdout as a completed validation result; do not tune on its outputs. Finish the running OCR holdout, then improve using development evidence and expand development coverage independently. A future modified extraction configuration needs a newly frozen untouched holdout. Automatic selection remains unpromoted. Runtime/helper tests pass but end-to-end automatic UX is still pending.

## Completion on 6 October 2026

The v4 failure above remains preserved. Expanded development to 11 identities and froze a fresh 9-identity holdout across English, Thai and bilingual resumes. Final v6 component gates passed without lowering thresholds. All six installed completion-capable configurations were compared for extraction and all three vision configurations for OCR. Policy v6 automatically uses Qwen 2.5 7B extraction and the validated Typhoon OCR order; normal uploads need no model selection.

Completed 40 regression tests and 36 live HTTP uploads across text, digital PDF, PNG and scanned PDF. Published SCORECARD.md, exact policy/digests, raw evidence and reproduction instructions. Browser verification and the completion audit accompany this delivery. Image identity and some image date/record accuracy remain below component thresholds: functional success is not error-free extraction. The tool requires human review of source documents. No cloud processing or new model downloads were introduced.
