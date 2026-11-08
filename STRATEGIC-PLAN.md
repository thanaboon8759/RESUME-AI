# Resume AI — review and strategic delivery plan

Date: 2 October 2026. Reviewed branch: `benchmark`, commit `d608f5ae8a862988e09177b07d696b2bf2bdb626`.

## Goal

Deliver an upload-triggered, local resume extraction workflow and testing frontend; choose the OCR and extraction models using reproducible Thai, English and bilingual evaluations. Preserve source evidence, expose failures and require human review. Success means reliable extraction, not automated hiring or candidate ranking.

The goal is saved in this Codex chat. The user selected **frontend uploads** as the trigger. This is an application workflow, not a scheduled Codex reminder.

## Executive decision

Keep the branch's local-first architecture, but treat it as a prototype. Use clean PDF text extraction before OCR. Evaluate OCR separately from structured extraction. Start the extraction comparison with the branch's `qwen2.5:7b`, `scb10x/typhoon2:8b` and `llama3.1:8b` candidates, using exact installed tags and model digests. These are existing-repository baselines, not a claim that they are today's best models. Include a newer local candidate only after confirming its license, available hardware and language coverage.

Use Qwen as the first baseline to test, **not as an approved production winner**. The live development comparison below supports retaining it for prototype experiments because it completed every attempt, but its skill extraction is below the acceptance target. No tested configuration is approved for production. Compare baseline Typhoon OCR against the configuration variant with crop held constant. The existing experiment changes both model and cropping, so it cannot isolate the cause of any improvement. Do not invest in further fine-tuning until clean baseline evaluations establish a meaningful error pattern.

## Branch review: findings in priority order

Source links below are pinned to the reviewed commit.

| Priority | Finding and evidence | Consequence / required change |
|---|---|---|
| P1 | [train_typhoon_qlora.py:169](https://github.com/thanaboon8759/RESUME-AI/blob/d608f5ae8a862988e09177b07d696b2bf2bdb626/train_typhoon_qlora.py#L169) saves `torch.randn(16,16)` as dummy adapter weights. [export_ollama_gguf.py:15](https://github.com/thanaboon8759/RESUME-AI/blob/d608f5ae8a862988e09177b07d696b2bf2bdb626/export_ollama_gguf.py#L15) references the base model without applying an adapter. Local base and fine-tuned manifests share weight blob `2c2720a40fa3732b175fb69bc5ec58f6b11e0267c770a10ae2726ca33c247b39`. | The fine-tuned label does not represent trained weights in this pipeline. Rename it as a prompt/configuration variant; remove unsupported training-success claims. Implement real training, validation, adapter loading/merging and weight provenance before claiming fine-tuning gains. |
| P1 | [web_ui.py:927–934](https://github.com/thanaboon8759/RESUME-AI/blob/d608f5ae8a862988e09177b07d696b2bf2bdb626/web_ui.py#L927) joins client filenames and sample paths directly to local directories. `/api/batch` also accepts arbitrary directories. | Traversal/absolute paths can escape intended roots. Generate internal filenames, constrain resolved sample paths and remove arbitrary directory access from any deployed service. |
| P1 | [web_ui.py:599](https://github.com/thanaboon8759/RESUME-AI/blob/d608f5ae8a862988e09177b07d696b2bf2bdb626/web_ui.py#L599) and other render paths interpolate model/document fields into `innerHTML`. | Untrusted resume text can become active browser markup. Use text nodes or vetted sanitization; test hostile strings. |
| P1 | [eval/benchmark.py:75](https://github.com/thanaboon8759/RESUME-AI/blob/d608f5ae8a862988e09177b07d696b2bf2bdb626/eval/benchmark.py#L75) assigns mock skill outputs by model name, then selects a winner and writes the same output path as live runs. The stored report lacks execution mode and provenance. | Mock rankings are predetermined; historical report cannot substantiate a live winner. Separate fixture/live outputs and disallow promotion from mock or unverifiable data. |
| P1 | [eval/benchmark.py:113](https://github.com/thanaboon8759/RESUME-AI/blob/d608f5ae8a862988e09177b07d696b2bf2bdb626/eval/benchmark.py#L113) averages F1 over successful outputs and selects by F1 alone. | An unreliable model can outrank a reliable one. Count failed samples as zero in all-attempt accuracy; enforce minimum success rate before ranking. |
| P1 | [web_ui.py](https://github.com/thanaboon8759/RESUME-AI/blob/d608f5ae8a862988e09177b07d696b2bf2bdb626/web_ui.py#L888) creates a candidate profile from the filename after extraction failures. | Failure can look like candidate data. Return an explicit error, no profile, and enable retry. |
| P2 | [eval_speed_accuracy.py:285](https://github.com/thanaboon8759/RESUME-AI/blob/d608f5ae8a862988e09177b07d696b2bf2bdb626/eval_speed_accuracy.py#L285) names a 1.5% CER gate but compares against 2.0%; display uses 2.5%. It excludes empty failed outputs from OCR averages. | Acceptance reports can mislead. Centralize thresholds, include failures, and report language-specific metrics with sample counts. |
| P2 | [finetune_results.json](https://github.com/thanaboon8759/RESUME-AI/blob/d608f5ae8a862988e09177b07d696b2bf2bdb626/benchmark_results/finetune_results.json) records CER 16.27% versus 16.06%, and skill F1 0.95 for both variants. | These artifacts do not demonstrate the stated Thai CER target or a meaningful fine-tuning gain. Raw predictions and repeated runs are needed. |
| P2 | [requirements.txt](https://github.com/thanaboon8759/RESUME-AI/blob/d608f5ae8a862988e09177b07d696b2bf2bdb626/requirements.txt) omits packages directly used by the app, including FastAPI, Uvicorn, multipart handling, pypdf and Typhoon OCR. Startup eagerly loads GPU/embedding components. | Fresh installation is not reproducible. Split minimal web, OCR and training dependencies; lazy-load optional engines and produce a lockfile. |
| P2 | [web_ui.py:69](https://github.com/thanaboon8759/RESUME-AI/blob/d608f5ae8a862988e09177b07d696b2bf2bdb626/web_ui.py#L69) loads a remote Tailwind script despite the air-gap claim; wildcard CORS is enabled. | Vendor static assets and constrain access. Validate offline execution with outbound networking disabled. |
| P2 | [eval/benchmark.py:54](https://github.com/thanaboon8759/RESUME-AI/blob/d608f5ae8a862988e09177b07d696b2bf2bdb626/eval/benchmark.py#L54) references an undefined `logger` in model-discovery error handling. | The recovery path can fail with NameError. Add a logger and an error-path test. |

These are static review findings, not a penetration test. Existing tests cover routing only; they do not establish extraction quality or service readiness.

## Target workflow

1. User chooses a resume and extraction model in the frontend.
2. Validate type, size, page count and parser limits. Assign an internal job identifier.
3. Extract text per page. Route scanned or garbled pages to the selected OCR engine.
4. Preserve source text with page/section provenance. Never silently truncate documents.
5. Run structured extraction with a fixed schema and prompt version. Treat document instructions as data.
6. Validate schema; attach evidence and unknown/missing fields. Separate parsing errors from inference errors.
7. Show source alongside fields, status, actual model, timing and warnings. Permit correction and deliberate JSON export.
8. For deployment, process jobs in an isolated worker with bounded retries, cancellation, cleanup and one GPU job at a time. Retain a metadata-only audit trail.

No candidate eligibility, personality, protected attributes, ranking or hire/reject recommendations are part of this scope.

## Model-selection experiment

**Dataset:** begin with 60 development and 60 sealed evaluation resumes, balanced across Thai, English and bilingual documents; use synthetic or consented/redacted material. Split by person and template family, not page. Include digital/scanned PDFs, tables, two-column layouts, DOCX, poor scans, absent fields, overlapping employment, Thai Buddhist dates, long documents and document prompt injection. Existing synthetic data is useful for smoke tests, not sufficient for a final choice. A reviewer creates field-level labels and evidence; a second reviewer adjudicates ambiguous examples.

**Bounded first pass:** at most three extraction candidates and two OCR configurations. Smoke-test ten development files, shortlist, then run the sealed set three times per candidate. No cloud spending or automatic model downloads. Stop on memory exhaustion, schema failure patterns, or a run exceeding the configured time budget; record the failure. Do not tune against the sealed set. Expand the dataset before a broad production rollout.

**Control variables:** same hardware, quantization, prompt/schema, generation limits, corpus and concurrency. Record cold startup separately from warm latency. Freeze OCR output for extraction-only comparisons. Run an end-to-end comparison after selecting each stage.

**Per-run ledger:** UUID, UTC time, git SHA, dataset hash, file hash, language/layout, model digest/tag/quantization, prompt/schema versions, OS/GPU/VRAM, warm/cold status, route, status/error, elapsed stage times, token counts, memory peak, raw output and score. Store identifiable raw documents/results only in controlled local test storage with explicit retention.

| Metric | Proposed gate for the pilot | Rationale |
|---|---|---|
| Schema-valid successful extractions | At least 98% overall; report each language separately | Reliability before ranking |
| Name/email/phone exact match | At least 98% where the field exists; separately measure correct nulls | Avoid identity and contact corruption |
| Explicit skill macro F1 | At least 0.95 on all attempts, failures score zero | No success-only denominator |
| Unsupported extracted facts | At most 1%; no fabricated name/contact in the sealed set | Grounding |
| Thai OCR character error rate | At most 1.5% if retaining the branch's existing target | Must be measured on Thai text, not mixed-language averages |
| End-to-end warm latency | Initial target p95 ≤30 seconds for a two-page document on the designated GPU | Revisit only with measured hardware data |
| Memory / stability | Fits selected hardware; no OOM or crash during repeat runs | Operability |
| Boundary tests | No path escape or executable markup; model failure never becomes a profile | Mandatory safety/correctness |

Targets are proposed acceptance criteria, not observed performance. Report per-language results, confidence intervals and sample sizes; small samples cannot prove a 1% rare-failure rate. If no candidate passes, select none and improve the failing stage.

**Selection rule:** apply correctness gates first; among passing configurations prefer highest critical-field accuracy, then lowest unsupported-fact rate, then fastest p95 and lowest measured resource cost. Treat differences within uncertainty as ties and prefer the simpler deployment. Self-reported model confidence never serves as calibrated accuracy. Local inference has hardware, electricity, support and review costs even when API cost is zero.

## Delivery phases and dependencies

| Phase | Deliverable | Exit gate | Planning estimate |
|---|---|---|---|
| 0 — Review and usable lab | This plan, active goal, upload console, parser tests | Sample parsing works; failures visible | Delivered prototype |
| 1 — Stabilize branch | Fix review findings, reproducible dependencies, separated live/mock reports | Boundary and regression tests green | 2–3 engineering days |
| 2 — Establish evidence | Labels, frozen manifests, live run ledger, baseline reports | No leakage; reproducible runs | 3–5 days plus annotation |
| 3 — Choose models | Stage-specific and end-to-end scorecards | All gates pass or explicit no-winner decision | 2–3 days after models/hardware ready |
| 4 — Integrate automation | Isolated job worker, bounded queue, retries/cancel, field evidence and correction UI | Upload-to-export and cleanup E2E tests pass | 3–5 days |
| 5 — Controlled pilot | Small representative workload, human review, error sampling, rollback | Accuracy/latency sustained; retention verified | 1 week observation |

Estimates assume one engineer, available local hardware and a domain reviewer. Annotation and model availability can dominate elapsed time.

## Frontend delivered now

`resume-lab/` is a standalone local prototype that reuses the branch's CandidateProfile schema. It supports automatic scanning on file selection, source-text preview without Ollama, local model selection, OCR integration, schema validation, JSON export, and an in-memory run history. UI assets are local and model content is rendered as text. Upload names never become filesystem paths. A session token, host/origin checks and loopback binding constrain the local endpoint.

This deliberately does not claim to repair or replace the original branch in GitHub. No remote commits or deployment were made. Integration can move the lab into the repository after phase 1, using a shared schema module instead of the bundled snapshot.

The prototype uses the documented Ollama schema request plus post-response Pydantic validation: [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs), [chat API](https://docs.ollama.com/api/chat). Its parser and worker boundaries still need isolation and hard time/memory limits before production.

## Validation and current dependencies

- Original branch router suite: **9 passed** with UTF-8 console encoding.
- Resume Lab parser and response-handling tests: **10 passed**. Mocked response tests are not accuracy measurements. JavaScript syntax check passed.
- HTTP checks verified upload filename sanitization and rejection of requests missing the session token. Browser verification confirmed synthetic text scanning and source inspection.
- The initial Ollama probe failed, then the existing runtime was located and started on loopback with `OLLAMA_NO_CLOUD=1`. GPU discovery confirmed an RTX 4080 with 16 GiB VRAM. No models were downloaded. Live extraction comparisons are now saved below.
- Scanned-PDF OCR requires the optional PyMuPDF dependency; it remains unverified here. Live image OCR smoke results are saved in `resume-lab/live-ocr-smoke.json`: base and configuration variant each recovered 5/5 target phrases from one simple English scan, in 11.09s and 5.92s respectively. Loading state differs, so these two timings are not a controlled speed comparison. A subsequent adapter fix unwraps Typhoon's JSON `text` envelope before extraction.
- Browser end-to-end verification: actual synthetic PNG upload triggered base Typhoon OCR and Qwen extraction, completing in **13.128 seconds**. Displayed profile correctly contained Jane Doe, jane@example.com, Python, AWS and Docker; missing fields were null/empty. Screenshot saved alongside this plan.
- Production model selection remains open until a representative labeled holdout passes the gates. This does not prevent using the delivered prototype for local testing.

## Live model comparison completed on this machine

Reports: `resume-lab/live-benchmark.json` (v1 prompt, 3 documents × 3 models) and `resume-lab/live-benchmark-v2.json` (v2 prompt, 5 documents × 2 models × 2 repetitions). These are **development smoke comparisons**, not production validation. All inference was local on the existing RTX 4080 through Ollama 0.34.0; temperature 0, 32,768 context, 4,096 output limit. Source, schema-validated profiles, per-attempt errors, model digests, token counts and hashes are retained in the reports. The benchmark counts failed attempts as zero.

| Configuration | Attempts | Valid output | Skill F1, all attempts | Name/email/phone exact match | Mean seconds | Observed p95 seconds |
|---|---:|---:|---:|---:|---:|---:|
| Qwen 2.5 7B, v1 | 3 | 100% | 0.667 | 100% | 5.92 | 8.66 |
| Llama 3.1 8B, v1 | 3 | 100% | 0.614 | 88.9% | 5.10 | 8.80 |
| DeepSeek R1 8B, v1 | 3 | 66.7% | 0.667 | 66.7% | 46.19 | 58.20 |
| Qwen 2.5 7B, v2 | 10 | 100% | 0.600 | 93.3% | 6.01 | 8.76 |
| Llama 3.1 8B, v2 | 10 | 80% | 0.788 | 73.3% | 13.77 | 49.76 |

The v1 and v2 rows use different sample sets and should not be interpreted as a controlled overall accuracy improvement. Same-document raw results permit focused comparisons. Times include loading when needed; this small sample's observed p95 is effectively its maximum, not a production-tail estimate.

**Observed failure modes:** Qwen copies grouped skill lines as single strings on bilingual and long Thai examples; Llama repeatedly produces invalid output on the longer Thai example; DeepSeek fails one of three schemas and is much slower under this output budget. Exact skill labels may omit skills stated elsewhere, and a bilingual name can legitimately include both scripts; review these disagreements instead of equating every mismatch with hallucination. Literal source matches are provided for inspection but are not a measured unsupported-fact rate.

**Cost comparison:** all three extraction candidates are local Q4_K_M models. Installed sizes are approximately Qwen 4.36 GiB, Llama 4.58 GiB and DeepSeek 4.87 GiB. There are no paid API calls in these runs. End-to-end duration and saved input/output token counts provide compute proxies; electricity, hardware depreciation and human review costs were not measured. At a common hardware hourly cost, the v1 DeepSeek run consumes roughly 7.8× Qwen's wall time per document, including startup/failure overhead; this is not an energy measurement.

**Decision:** no production winner. Use Qwen only as the initial frontend test baseline and keep model selection explicit. Next work is to fix/validate atomic skill output, refine labels and missing-field coverage, then rerun a sealed, independently labeled holdout. Do not claim 95% skill extraction or a successfully fine-tuned OCR model from the current branch.

## Rollout and rollback

Version a single configuration containing extraction/OCR model digests, prompt/schema versions, limits and routing thresholds. Keep the prior passing configuration. Promote only with the scorecard and human review; roll back on regression, rising parse failure or latency. Disable AI extraction while preserving text inspection when no healthy validated model is available. Do not silently swap to a different model. Before network deployment add authentication, authorization, TLS, isolated parsers, request quotas, deletion controls, dependency scanning and a reproducible offline installation bundle.
