# Browser verification

Local app: http://127.0.0.1:8765/ . Synthetic resumes only; processing stayed local.

Checks observed on 5 October 2026, with the Thai upload repeated and captured on 6 October:

- Initial view reports automatic readiness, has no extraction/OCR model selectors, and defaults to full profile extraction (text-preview checkbox unchecked).
- Uploaded corpus-v2/hold2_th_2-scan.pdf through the actual file chooser. The repeat completed in 24.123 seconds (including local model load effects), showed PDF text + OCR, live extraction/schema valid, and selected the readable resume view automatically. Thai name, contact fields, Python/Pandas/SQL, two jobs, Thai date strings and education were visible. Earlier diagnostics showed policy v6, Qwen extraction and the primary Typhoon OCR configuration with successful attempt provenance.
- Synthetic text sample ran live Qwen extraction after fixing the preview-only default. Mira Example appeared with three skills, employment and education. Source and JSON tabs showed the corresponding text/structured result; absent phone remained null.
- Empty file upload displayed a nonempty-file error, explicitly reported that no candidate profile was created, and disabled export.
- The UI visibly warns that schema validity does not prove factual accuracy and OCR can change characters and dates.

Saved repeat evidence: [Thai readable result](browser-thai-auto.png) and [accessibility snapshot](browser-thai-auto.txt). The app tab was retained for the user. This is a functional browser check, not an additional accuracy benchmark. The complete scored pipeline report is upload-verification-v6/summary.json; known scanned-document errors remain documented in SCORECARD.md.

JSON export implementation exists, but browser download completion was not verified (the earlier in-app download wait timed out). No claim of verified download behavior is made.
