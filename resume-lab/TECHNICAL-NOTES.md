# Resume Lab — automatic local scanning

Upload a resume to get readable text, structured facts and optional diagnostics. Models are selected automatically from evaluated local configurations. Based on DUMB-DOG-AI benchmark branch commit d608f5ae8a862988e09177b07d696b2bf2bdb626; the original repository is preserved under work/repo.

## Run

Requires Python 3.10+, Ollama and the exact installed model digests in model-policy.json. Tested with Ollama 0.34.0 and an RTX 4080. No model downloads or cloud API calls are made by the app.

```powershell
python -m pip install -r requirements.txt
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
ollama serve
```

In a second terminal in this folder:

```powershell
python server.py
```

Open [Resume Lab](http://127.0.0.1:8765/). Choose a file or click **Try a synthetic text sample**. Full extraction is enabled by default. **Text preview only** skips profile extraction (images still need OCR). Compare **Readable resume** with **Source text**. **Scan diagnostics** shows actual models, fallback attempts and exact-source repairs. **Export JSON** saves the complete result, including source text and provenance.

## Selection policy

- Extraction: qwen2.5:7b.
- OCR: typhoon-ocr-finetuned:latest, with typhoon-fast:latest then scb10x/typhoon-ocr-3b:latest as fallbacks.
- The OCR variants share base weights. The tag named finetuned is a configuration name, not evidence of successful adapter training.
- Frozen development ranking and held-out gates precede speed. The first two OCR configurations were essentially tied on development CER; latency broke the tie. The fast variant did better on the later holdout, which was not used to reorder them.
- Only tested digests and capabilities are eligible. Prompt, schema, parser or source-repair changes invalidate the runtime policy.
- Only Qwen qualified for extraction. If it is absent or fails, an explicit error is returned; no unqualified extractor or fabricated profile is substituted.

See [scorecard](evaluation/SCORECARD.md), [selection protocol](evaluation/SELECTION-PROTOCOL.md) and [policy](model-policy.json).

## Accuracy and limits

The final synthetic holdout has nine identities, three per language group; development has eleven. Four formats per identity are correlated renderings. The earlier failed six-case holdout is retained. Synthetic development and holdout share generator rules: these scores do not establish real-world template generalization.

The fresh text holdout scored 100% on identity and skills, 96.8% on employment/education, and 90.7% on dates. All 36 HTTP upload checks succeeded, but image-based identity accuracy was **92.6%**, and image date accuracy **84.1%**. Component gates passed; end-to-end OCR still introduces meaningful errors. Review names, contacts and dates against the original. Valid JSON is not proof of factual accuracy.

- PDF, DOCX, PNG/JPEG, UTF-8 TXT/MD: 8 MB, 10 PDF pages, 60,000 extracted characters. AI input additionally limited to 24,000 UTF-8 bytes.
- Readable PDF pages use embedded text; short/garbled pages use Pdfium OCR. This is a basic heuristic, not a comprehensive Thai encoding detector.
- DOCX tables follow paragraphs. Exact interleaving, headers, footers and embedded-image OCR are unsupported.
- Thai synthetic rendering uses Tahoma without RAQM. CER normalizes Unicode, whitespace and case, not spelling.
- One active scan at a time; no durable queue or recurring schedule. Automation is triggered by upload.
- Uploaded content and history stay in process/browser memory. Explicit export includes resume content. Browser/Ollama retention is outside the app's control.
- No candidate ranking, hiring recommendations, inferred seniority/experience totals or model self-confidence.
- Loopback testing prototype, not a production deployment. Original branch findings remain in ../STRATEGIC-PLAN.md.

## Tests and reproducibility

```powershell
python -m unittest -v test_lab test_evaluation test_auto_policy test_source_facts test_automatic_scan test_policy_evidence
node --check app.js
python manage_policy.py promote --id v6 --extraction fresh-holdout-extraction-v6 --ocr fresh-holdout-ocr-v6
```

The last command makes no inference: it checks frozen gates, corpus/model hashes, source snapshots and recomputed scores, preserving an identical existing policy. Tests also need reportlab. Static analyzers were unavailable in the tested environment.

Live examples (new run identifiers preserve historical evidence):

```powershell
python evaluate_models.py --stage extraction --split development --corpus corpus-v2 --run my-development-run --models qwen2.5:7b
python evaluate_models.py --stage ocr --split development --corpus corpus-v2 --run my-ocr-run
python verify_uploads.py
```

Upload verification calls the running app and resumes identical saved verification rather than repeating completed uploads. Avoid concurrent browser scans during benchmarks. Raw replies, failures, digests, tokens/load counters and post-request resident memory observations are under evaluation/runs. These are cost proxies, not energy, peak memory or monetary measurements.

For changed inference, improve on development data, freeze candidate order with manage_policy.py freeze, and validate against a newly reserved holdout. Both provided corpora are now evaluated and cannot be called untouched in future experiments. Historical scripts/snapshots are retained for audit and are not all current entry points.

