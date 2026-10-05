# Selection protocol — frozen before held-out inference

This is a local resume transcription/extraction pilot for mandatory human review. It does not validate hiring decisions or population-wide accuracy. All installed completion/vision candidates have development attempts, including failures. No model name, claimed fine-tuning or self-confidence is evidence of quality.

## Eligibility and ranking

Extraction must achieve 100% schema success, identity exactness at least 0.95, skill F1 at least 0.90, employment/education field exactness at least 0.85, dates at least 0.90, record precision at least 0.95 and literal evidence at least 0.95. These are macro means including failures. A model failing any gate is excluded from automatic use. Record precision checks organization matching, not correctness of every field. Literal evidence is a conservative substring check, not semantic factuality. All per-sample differences remain available for review.

Among eligible extraction configurations rank by the arithmetic mean of identity, skill F1, employment/education exactness, date exactness, record precision and literal evidence. Accuracy precedes speed; use mean inference latency only to break ties within 0.001 of that score. Do not average incompatible historical scoring definitions.

OCR must complete every sample without output truncation, achieve mean normalized CER no greater than 0.05 overall and no greater than 0.08 for each language group. Rank by lowest overall CER; use latency only for a CER tie within 0.001. Report individual Thai character/date differences even when aggregate gates pass. Configuration variants sharing weights remain separate configurations, not independent model families.

## Holdout and promotion

Freeze inference prompts, schema, options, development annotations and ordered candidates before evaluating holdout. Run all eligible finalists, preserving raw replies, exact model digests, input/configuration hashes and failure denominators. Promote the highest development-ranked candidate that also meets every applicable held-out gate; retain other passing finalists in their development rank order as fallbacks. Do not tune on these held-out outputs. If none passes, record the failed validation, improve only on development evidence, and create a genuinely new untouched holdout before any subsequent promotion.

No language-specific winner will be inferred from one or two cases. A common policy will be used unless a larger independent comparison justifies language routing. Digital PDFs use embedded text when readable; image-only and unreadable pages use OCR. Test end-to-end extraction from OCR separately from extraction of reference text, including scanned PDF rendering, so good component results cannot conceal integration regressions.

Runtime only uses installed names with the tested digests and capabilities. Try a passing fallback after operational or validation failure; never substitute an unknown model or fabricate a profile. If no evaluated model is usable, report an explicit error. Missing fields may remain absent. Surface actual models, attempts, source text and warnings in the result. Tests must cover fallback and failure paths independently of a live healthy service.

## Reproducibility limits

The frozen corpus has five development and six holdout identities; four file formats per identity are correlated renderings, not 44 independent resumes. Thai rendering uses Tahoma without RAQM. CER normalizes Unicode, case and whitespace, but not spelling or punctuation. Development fixtures include literal Markdown. P95 from five/six samples is unstable; token counts, latency and post-request resident memory are resource proxies, not peak memory, energy or money. Repeated inference can differ despite temperature zero. No claims extend beyond the tested local digests and configuration.
