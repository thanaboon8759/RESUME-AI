import re
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import seed_db

ROOT = Path(__file__).resolve().parent.parent
PASSWORD_LITERAL = re.compile(r'password["\']?\s*[:=]\s*["\'][^"\']+["\']', re.IGNORECASE)


def test_no_hardcoded_passwords():
    # The repo is public: a password written in code is a published password.
    files = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    offenders = [f for f in files if not f.startswith("tests/")
                 and PASSWORD_LITERAL.search((ROOT / f).read_text(encoding="utf-8", errors="ignore"))]
    assert offenders == []


@pytest.fixture
def client(monkeypatch):
    sb = MagicMock()
    monkeypatch.setattr(seed_db, "supabase", sb)
    return sb


def test_seed_requires_credentials_from_env(monkeypatch, client):
    monkeypatch.delenv("SEED_EMAIL", raising=False)
    monkeypatch.delenv("SEED_PASSWORD", raising=False)
    with pytest.raises(SystemExit):
        seed_db.seed()
    client.auth.sign_in_with_password.assert_not_called()


def test_seed_stops_when_login_fails(monkeypatch, client, capsys):
    monkeypatch.setenv("SEED_EMAIL", "hr@example.com")
    monkeypatch.setenv("SEED_PASSWORD", "not-a-real-one")
    client.auth.sign_in_with_password.side_effect = Exception("bad login")
    with pytest.raises(SystemExit):
        seed_db.seed()
    client.table.assert_not_called()
    assert "fixtures" not in capsys.readouterr().out  # stopped at the login, not later for another reason


def test_stale_files_are_gone():
    for name in ["recreate_api.py", "init_admin.py", "test_login.py", "test.pdf", "package.json",
                 "package-lock.json", "app/database/seed/generate_seed.py", "app/database/seed/seed.sql"]:
        assert not (ROOT / name).exists(), name


def test_replacement_keeps_structure():
    from tests.test_real_resume_validation import PROJECT_KEYWORDS, SAMPLE_RESUME
    ids = re.findall(r"\[ID: b(\d+)\]", SAMPLE_RESUME)
    assert ids == [str(i) for i in range(len(ids))] and len(ids) >= 20  # b0..bN, in order, no gaps
    assert all(k.split()[0] in SAMPLE_RESUME.lower() for k in PROJECT_KEYWORDS)
    assert "narin.example@example.com" in SAMPLE_RESUME


def test_pyflakes_clean():
    import sys
    out = subprocess.run([sys.executable, "-m", "pyflakes", "app", "seed_db.py", "e2e_test.py"],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.stdout.strip() == "", out.stdout


def test_local_run_logs_are_ignored():
    # Local logs of live runs can hold real resume text; they must never be committable.
    r = subprocess.run(["git", "check-ignore", "-q", ".superpowers/live-local-1.txt"], cwd=ROOT)
    assert r.returncode == 0


def test_test_resumes_use_example_contacts():
    # Contacts in tests must be obviously fake: example.com addresses and the 080-000-0000 phone.
    files = subprocess.run(["git", "ls-files", "tests"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    bad = []
    for f in files:
        text = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
        bad += [f"{f}: email" for e in re.findall(r"[\w.+-]+@([\w-]+\.[\w.]+)", text) if e not in ("example.com", "example.org")]
        bad += [f"{f}: phone" for p in re.findall(r"\b0\d{1,2}[- ]?\d{3}[- ]?\d{4}\b", text) if p != "080-000-0000"]
    assert bad == []


ORG_WORD = re.compile(r".*\b(University|College|School|Institute|Co\.,? ?Ltd|Company)\b.*")


def test_test_resumes_use_example_orgs():
    from tests.test_real_resume_validation import SAMPLE_RESUME
    bad = [m.group(0) for m in ORG_WORD.finditer(SAMPLE_RESUME) if "Example" not in m.group(0)]
    assert not bad, f"{len(bad)} line(s) name a real organisation"  # count only: CI logs must not echo names
