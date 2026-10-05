# Test run — 6 October 2026

Status: completed. 40/40 regression tests passed; JavaScript syntax check passed. Live policy v6 was ready. All 36 fresh token-protected uploads succeeded and asserted automatic selection plus correct OCR routing. These are repeated regression fixtures, not a new untouched holdout. No inference, ranking or application code was changed.

| Format | Success | Identity exact | Skill F1 | Date exact | Mean seconds |
|---|---:|---:|---:|---:|---:|
| Text | 9/9 | 100% | 100% | 90.7% | 2.94 |
| Digital PDF | 9/9 | 100% | 100% | 97.2% | 2.91 |
| PNG | 9/9 | 92.6% | 100% | 84.1% | 12.89 |
| Scanned PDF | 9/9 | 92.6% | 100% | 90.7% | 9.97 |

The nine identities include three English, three Thai and three bilingual resumes. The four formats are correlated renderings. Accuracy reproduced the previous integration results; latency varied. PNG record precision remains 88.9%. Scanned names and dates require human review; successful processing is not perfect extraction.

Browser inspection confirmed the retained Thai readable profile, automatic-ready state, unchecked preview-only option, absent model selectors and visible factual-accuracy warning. This read-only check inspected the earlier displayed Thai upload; fresh uploads in this run were performed through HTTP. See browser-state.txt.

Evidence: [tests](tests.txt), [JavaScript check](javascript-check.txt), [live policy](live-policy.json), [summary](summary.json), [complete attempts](attempts.jsonl), [configuration hashes](configuration.json). Prior benchmark reports are unchanged. The unchanged frozen policy uses Qwen extraction and the validated Typhoon OCR order. No cloud services or downloads were used.
