import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# Synthetic or public example resumes only: a real person's resume was once published here.
APPROVED_SAMPLES = {"bilingual_resume.pdf", "english_resume.pdf", "real_functional_resume.pdf",
                    "scanned_resume.png", "thai_resume.pdf"}


def test_only_approved_samples():
    found = {p.name for p in (ROOT / "benchmark_data").iterdir() if p.is_file()}
    assert found <= APPROVED_SAMPLES, sorted(found - APPROVED_SAMPLES)


def test_ui_samples_exist():
    src = (ROOT / "web_ui.py").read_text(encoding="utf-8")
    for name in set(re.findall(r"loadSample\('([^']+)'\)", src)) | set(re.findall(r"selectedSample = '([^']+)'", src)):
        assert (ROOT / "benchmark_data" / name).exists(), name


def test_web_ui_has_no_open_cors_and_uses_path_rules():
    src = (ROOT / "web_ui.py").read_text(encoding="utf-8")
    assert 'allow_origins=["*"]' not in src
    assert "resolve_sample(" in src and "resolve_batch_dir(" in src and "safe_upload_name(" in src


def test_no_undefined_names():
    import importlib.util, subprocess, sys
    assert importlib.util.find_spec("pyflakes"), "install requirements-dev.txt"  # else the run below passes empty
    files = [f for f in subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True).stdout.split()
             if not f.startswith("resume-lab/evaluation/runs/")]  # frozen historical copies
    out = subprocess.run([sys.executable, "-m", "pyflakes", *files], cwd=ROOT, capture_output=True, text=True).stdout
    assert [l for l in out.splitlines() if "undefined name" in l] == []


def test_web_ui_installs_guards():
    assert "install_guards(app)" in (ROOT / "web_ui.py").read_text(encoding="utf-8")
