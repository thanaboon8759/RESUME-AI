# SDD ledger — plan: docs/superpowers/plans/2026-11-08-ocr-compare-and-adopt.md
Task 1: complete (commit 5b7d2e0) — compare_ocr.py, 7 tests; real run on 4 files.
Task 4: complete (commit 0a9df27 on feat/local-ocr) — 4 tests; live Thai scan CER 0.0; suite 47 passed + 5 known main failures.
Task 4: Ruling: also changed the OCR log line to name the provider (was hard-coded "Typhoon OCR") — misleading logs otherwise — cost if wrong: none.
Task 2: complete — v7-qlora-dev-ocr reproduces all CERs exactly; rank 1 typhoon-ocr-qlora-v1-rp1 unchanged.
Task 2: Ruling: below rank 1 the tool's ordered() differs from the hand-made frozen-candidates-v7.json (latency tie-breaks in one run); the tool's order is authoritative for the policy — cost if wrong: fallback order only.
Task 3: complete — manage_policy --ocr-holdout-corpus (3 tests incl. v6 reproduction); v7-qlora frozen+promoted; app selection_status ready, live upload used typhoon-ocr-qlora-v1-rp1, exact name/skills.
Task 3: test fix — v6 reproduction compares to origin/benchmark policy (live file is v7 now); suite 30/30.
Final (Part C): fixed empty OCR output passed silently — test_local_ocr_rejects_empty_output RED→GREEN; fixed no page-count/size limits — test_local_ocr_rejects_too_many_pages + test_local_ocr_clamps_huge_pages RED→GREEN; fixed (re-graded Minor→Important, privacy) OCR_PROVIDER typo silently uploads to cloud — test_provider_value_is_strict RED→GREEN; suite 51 passed + 5 known main failures.
Final (A/B): fixed compare report hides that OCR never ran — test_rows_show_when_ocr_never_ran RED→GREEN; fixed (re-graded Minor→Important, defeats the tool's purpose) default run compares one model after v7 — test_default_models_compare_policy_default_with_previous_default RED→GREEN; suite 32/32.
Final (A/B): fixed SCORECARD rank column, promotion file name, post-holdout fallback re-ranking disclosure, owner acceptance of the export override (wording; no test).
Final: minor (deferred): compare_ocr uses any sibling .txt as reference; misses .md references
Final: minor (deferred): compare_ocr reads whole file before the 8 MB check; char-level diff can be slow on very different 60k-char outputs
Final: minor (deferred): test_manage_policy v6 test needs a local origin/benchmark ref
Final: minor (deferred): no test pinning freeze-with-flag/promote-without (logic verified correct by reviewer)
Final: minor (deferred): manage_policy.py whole-file CRLF conversion inflates the diff
Final: minor (deferred, local OCR): partial JSON not rejected; get_pixmap blocks the event loop; fitz doc not closed; README doesn't mention new env vars
