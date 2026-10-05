# Completion audit — automatic resume scanning

Completed 6 October 2026. Scope: installed local models and a frontend upload trigger.

| Requirement | Delivered evidence |
|---|---|
| Compare all suitable installed AI configurations | SCORECARD.md: six extraction configurations and three OCR configurations; runs retain failures and raw responses |
| English, Thai, bilingual and document formats | corpus-v2 manifest; 11 development and 9 fresh held-out identities; upload-verification-v6 covers four formats |
| Preserve independent evaluation | Original failed v4 holdout retained; frozen-candidates-v6.json, SELECTION-PROTOCOL.md and promotion-v6.json bind fresh evaluation |
| Improve source fidelity | Required schema, source_facts.py conservative grounded corrections, OCR context/wrapper handling; corresponding regression tests |
| Choose models automatically | ../model-policy.json validated v6; ../automatic_scan.py and ../auto_policy.py enforce stage order, digest and engine pins |
| No required model choice | Frontend upload directly runs extraction, adds OCR when necessary; optional diagnostics disclose actual models |
| Verified failures and fallbacks | final-tests.txt: 40 passing tests including missing/changed models, invalid profiles, fallback provenance and total failure |
| Full pipeline and readable output | 36/36 functional HTTP upload successes; BROWSER-VERIFICATION.md records actual browser checks |
| Reproducibility and review | SCORECARD.md, ../README.md, source/evaluator snapshots and raw logs; code reviews resolved promotion-integrity and grounded-repair findings |

The model ranking was frozen from development before fresh holdout results. Qwen is the only qualified extraction model; unavailable extraction fails explicitly. OCR tries only validated configurations. Shared Typhoon weights and the misleading finetuned tag are disclosed in the scorecard.

Completion means the evaluated automatic selection workflow and evidence are delivered, not production accuracy certification. PNG identity 92.6%, dates 84.1%, record precision 88.9%; scanned PDF identity 92.6%. These are below corresponding component thresholds. The synthetic set is small and shares generation/layout conventions, so it cannot establish real-world generalization. No language-specific routing was justified. Human review remains necessary, especially for scanned names, contacts and dates. No hiring decision is automated.

Browser download completion was not verified. Resource observations are token/latency/resident-memory proxies, not peak VRAM or monetary costs. The refreshed archive excludes Python bytecode caches and includes the app, policy, corpus, reports and browser evidence.
