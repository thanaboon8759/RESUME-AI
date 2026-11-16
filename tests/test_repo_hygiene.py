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
