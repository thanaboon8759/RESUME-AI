# DUMB DOG AI

A local tool for turning English and Thai resumes into readable, structured information.

Upload a resume and the app picks the tested extraction and OCR models for you. You can review the result alongside the source and export it as JSON. Resume processing uses local Ollama models.

## Try it

You need Python 3.10+, Ollama, and the model versions listed in [the setup notes](resume-lab/TECHNICAL-NOTES.md). The included policy is tied to the tested model versions; it will tell you when a required model is missing or has changed.

With Ollama running, open a terminal in this repository:

```sh
cd resume-lab
python -m pip install -r requirements.txt
python server.py
```

Open **http://127.0.0.1:8765**, then upload a PDF, DOCX, image or text file. You can also click **Try a synthetic text sample** to see how it works.

## What to expect

The app uses Qwen for extraction and Typhoon for OCR when a document needs it. There are no model dropdowns to configure.

This is a testing tool, so check the result before using it. Scanned names and dates can still be wrong. It does not rank candidates or make hiring decisions.

## Tests and details

The latest run passed 40 regression tests and processed all 36 test uploads. That means the workflow completed, not that every extracted detail was correct.

- [Latest test report](resume-lab/evaluation/test-run-2026-10-06/REPORT.md)
- [Model comparison and accuracy](resume-lab/evaluation/SCORECARD.md)
- [Setup, troubleshooting and test commands](resume-lab/TECHNICAL-NOTES.md)

The browser app lives in `resume-lab/`. Earlier pipeline and training experiments remain in the other folders; their [original notes](docs/LEGACY-README.md) are kept for reference and may contain outdated claims.
