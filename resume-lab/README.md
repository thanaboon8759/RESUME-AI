# Resume Lab

Upload an English or Thai resume and get a readable profile you can check against the source. Model selection happens automatically, and processing stays local.

## Start the app

You need Python 3.10+, a running Ollama service, and the tested models described in [the setup notes](TECHNICAL-NOTES.md).

```sh
python -m pip install -r requirements.txt
python server.py
```

Open **http://127.0.0.1:8765**. Choose a resume or try the synthetic text sample. Use **Source text** to check the readable result and **Export JSON** to save it.

PDF, DOCX, PNG, JPEG, TXT and Markdown are supported, up to 8 MB. Images and scanned PDFs use OCR automatically.

Please check names, contacts and dates before using the result. OCR can make mistakes, and this app does not make hiring decisions.

[Setup and test commands](TECHNICAL-NOTES.md) · [Latest test report](evaluation/test-run-2026-10-06/REPORT.md) · [Model comparison](evaluation/SCORECARD.md)
