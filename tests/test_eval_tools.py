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
