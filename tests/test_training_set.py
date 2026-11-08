import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "resume-lab")
from build_training_set import build_holdout_v3, build_training_set  # noqa: E402

EVAL = Path("resume-lab/evaluation/corpus-v2/manifest.json")


def names_in(path):
    return {s["truth"]["full_name"] for s in json.loads(Path(path).read_text(encoding="utf-8"))["samples"]}


def text_hashes(manifest):
    return {s["text_sha256"] for s in manifest["samples"]}


def eval_text_hashes():
    return {s["sha256"]["text"] for s in json.loads(EVAL.read_text(encoding="utf-8"))["samples"] if "sha256" in s}


def test_training_identities_disjoint_from_eval(tmp_path):
    train = build_training_set(tmp_path / "t", n_train=12, n_val=4, seed=7)
    hold = build_holdout_v3(tmp_path / "h", n=9, seed=99)
    train_names = {s["truth"]["full_name"] for s in train["samples"]}
    hold_names = {s["truth"]["full_name"] for s in hold["samples"]}
    assert not train_names & names_in(EVAL)
    assert not hold_names & names_in(EVAL)
    assert not train_names & hold_names
    assert not text_hashes(train) & (text_hashes(hold) | eval_text_hashes())


def test_language_mix_matches_eval(tmp_path):
    train = build_training_set(tmp_path / "t", n_train=30, n_val=6, seed=7)
    langs = Counter(s["language"] for s in train["samples"])
    assert set(langs) == {"en", "th", "bi"} and min(langs.values()) >= 8


def test_holdout_is_evaluator_readable(tmp_path):
    hold = build_holdout_v3(tmp_path / "h", n=3, seed=99)
    assert hold["annotations_frozen"] is True
    s = hold["samples"][0]
    assert s["split"] == "holdout" and (tmp_path / "h" / s["files"]["image"]).exists()
    assert (tmp_path / "h" / "manifest.json").exists()
