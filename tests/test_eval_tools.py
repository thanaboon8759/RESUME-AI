import json
import sys
from pathlib import Path

sys.path.insert(0, "resume-lab")


def test_evaluator_accepts_corpus_v3():
    import evaluate_models
    assert "corpus-v3" in evaluate_models.CORPORA
    assert (evaluate_models.ROOT / "evaluation" / "corpus-v3" / "manifest.json").exists()


def test_strip_markup_removes_only_formatting():
    from format_share import strip_markup
    raw = json.dumps({"natural_text": "# Alice Smith" + chr(10) + "**Email:** alice@example.com" + chr(10) + "## Skills" + chr(10) + "- Python, SQL"})
    assert strip_markup(raw) == "Alice Smith\nEmail: alice@example.com\nSkills\n- Python, SQL"
    assert strip_markup("Plain text - kept") == "Plain text - kept"


def test_markup_free_cer_strips_both_sides():
    from format_share import markup_free_cer
    out = json.dumps({"natural_text": "Alice Smith" + chr(10) + "Email: a@b.co"})
    assert markup_free_cer("# Alice Smith" + chr(10) + "**Email:** a@b.co", out) == 0.0


def test_promoted_serving_config_is_committed():
    from pathlib import Path
    mf = Path("resume-lab/modelfiles/typhoon-ocr-qlora-v1-rp1.Modelfile").read_text(encoding="utf-8")
    assert "FROM typhoon-ocr-qlora-v1:latest" in mf and "PARAMETER repeat_penalty 1.0" in mf
