"""Runs the real manage_policy freeze/promote on a throwaway copy of resume-lab (no Ollama calls)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

LAB = Path("resume-lab").resolve()


@pytest.fixture
def lab(tmp_path):
    dst = tmp_path / "resume-lab"
    shutil.copytree(LAB, dst, ignore=shutil.ignore_patterns("training", "__pycache__", "*.png", "*.pdf"))
    for stale in ["model-policy.json"]:
        (dst / stale).unlink(missing_ok=True)
    return dst


def run(lab, *args):
    return subprocess.run([sys.executable, "manage_policy.py", *args], cwd=lab, capture_output=True, text=True,
                          encoding="utf-8")


def freeze_and_promote(lab, pid, dev_ocr, hold_ocr, extra=()):
    f = run(lab, "freeze", "--id", pid, "--extraction", "grounded-extraction-v6", "--ocr", dev_ocr, *extra)
    assert f.returncode == 0, f.stderr + f.stdout
    return run(lab, "promote", "--id", pid, "--extraction", "fresh-holdout-extraction-v6", "--ocr", hold_ocr, *extra)


def test_default_ocr_holdout_corpus_keeps_v6_behaviour(lab):
    p = freeze_and_promote(lab, "t6", "expanded-ocr-v5", "fresh-holdout-ocr-v6")
    assert p.returncode == 0, p.stderr + p.stdout
    new = json.loads((lab / "model-policy.json").read_text())
    old = json.loads((LAB / "model-policy.json").read_text())
    assert "ocr_holdout_corpus" not in new
    for key in ["ocr", "extraction", "development", "holdout", "corpus_sha256", "engine_sha256"]:
        assert new[key] == old[key], key


def test_ocr_holdout_uses_its_own_manifest(lab):
    p = freeze_and_promote(lab, "t7", "v7-qlora-dev-ocr", "qlora-v1-holdout", ("--ocr-holdout-corpus", "corpus-v3"))
    assert p.returncode == 0, p.stderr + p.stdout
    policy = json.loads((lab / "model-policy.json").read_text())
    assert policy["ocr"][0]["name"] == "typhoon-ocr-qlora-v1-rp1:latest"
    assert policy["ocr_holdout_corpus"] == "corpus-v3"
    assert policy["extraction"][0]["name"] == "qwen2.5:7b"
    # Without the flag the same corpus-v3 run must be refused (checked against corpus-v2's manifest).
    p2 = freeze_and_promote(lab, "t7b", "v7-qlora-dev-ocr", "qlora-v1-holdout")
    assert p2.returncode != 0 and "corpus mismatch" in (p2.stderr + p2.stdout)


def test_promote_rejects_digest_mismatch(lab):
    cfg = lab / "evaluation/runs/qlora-v1-holdout/summary.json"
    report = json.loads(cfg.read_text())
    report["configuration"]["models"][0]["digest"] = "0" * 64
    cfg.write_text(json.dumps(report))
    p = freeze_and_promote(lab, "t7c", "v7-qlora-dev-ocr", "qlora-v1-holdout", ("--ocr-holdout-corpus", "corpus-v3"))
    assert p.returncode != 0
