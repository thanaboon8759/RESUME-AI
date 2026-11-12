from pathlib import Path

import pytest

import train_typhoon_qlora as t

SAMPLES = [{"image": "a.png", "text": "a"}]


def test_train_refuses_empty_train_split(tmp_path):
    with pytest.raises(ValueError, match="split 'train'"):
        t._check_train_inputs(tmp_path / "run", [], SAMPLES)


def test_train_refuses_empty_val_split(tmp_path):
    with pytest.raises(ValueError, match="split 'val'"):
        t._check_train_inputs(tmp_path / "run", SAMPLES, [])


def test_train_refuses_reused_out(tmp_path):
    (tmp_path / "train_log.jsonl").write_text("{}\n")
    with pytest.raises(ValueError, match="already holds a training run"):
        t._check_train_inputs(tmp_path, SAMPLES, SAMPLES)


def test_train_guard_accepts_new_dir(tmp_path):
    assert t._check_train_inputs(tmp_path / "new", SAMPLES, SAMPLES) is None


def test_merge_refuses_base_dir(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    (base / "config.json").write_text("{}")
    for out in (Path(str(base) + "/"), base / ".." / "base"):
        with pytest.raises(ValueError, match="base model directory"):
            t._check_merge_out(base, out)


def test_merge_refuses_nonempty_dir(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep.txt").write_text("x")
    with pytest.raises(ValueError, match="not empty"):
        t._check_merge_out(tmp_path / "base", out)
    assert (out / "keep.txt").exists()


def test_merge_guard_accepts_new_dir(tmp_path):
    assert t._check_merge_out(tmp_path / "base", tmp_path / "out") is None


def test_merge_guard_accepts_empty_dir(tmp_path):
    (tmp_path / "out").mkdir()
    assert t._check_merge_out(tmp_path / "base", tmp_path / "out") is None


def test_train_checks_before_cuda(tmp_path, monkeypatch):
    def no_cuda():
        raise AssertionError("cuda touched")

    monkeypatch.setattr(t, "load_samples", lambda split, data_dir=None: [])
    monkeypatch.setattr(t, "_require_cuda", no_cuda)
    with pytest.raises(ValueError):
        t.train(out_dir=tmp_path / "run")
