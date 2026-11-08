import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, "resume-lab")
from compare_ocr import compare, write_report  # noqa: E402


@pytest.fixture
def fake_runner():
    calls = defaultdict(int)

    def run(image, model):
        calls[model] += 1
        return f"{model} page{calls[model]}"
    return run


def png(path, color="white"):
    Image.new("RGB", (400, 300), color).save(path)
    return path


def scanned_pdf(path, pages=2):
    images = [Image.new("RGB", (400, 300), "white") for _ in range(pages)]
    images[0].save(path, "PDF", save_all=True, append_images=images[1:])
    return path


def test_compare_runs_each_model_on_each_file(tmp_path, fake_runner):
    rows = compare([png(tmp_path / "a.png"), png(tmp_path / "b.png")], ["A", "B"], runner=fake_runner)
    assert [(Path(r["file"]).name, r["model"]) for r in rows] == [("a.png", "A"), ("a.png", "B"), ("b.png", "A"), ("b.png", "B")]
    assert all(r["ok"] and r["seconds"] >= 0 for r in rows)


def test_compare_handles_multipage_pdf(tmp_path, fake_runner):
    rows = compare([scanned_pdf(tmp_path / "two.pdf")], ["A"], runner=fake_runner)
    assert rows[0]["ok"] and rows[0]["text"] == "A page1\n\nA page2"


def test_compare_records_model_error(tmp_path, fake_runner):
    def runner(image, model):
        if model == "B":
            raise RuntimeError("model not found")
        return fake_runner(image, model)
    rows = compare([png(tmp_path / "a.png")], ["A", "B"], runner=runner)
    assert rows[0]["ok"] and not rows[1]["ok"] and "model not found" in rows[1]["error"]


def test_cer_only_when_reference_exists(tmp_path, fake_runner):
    (tmp_path / "x.txt").write_text("A page1", encoding="utf-8")
    (tmp_path / "y-scan.txt").write_text("unused", encoding="utf-8")
    rows = compare([png(tmp_path / "x.png"), png(tmp_path / "z.png")], ["A"], runner=fake_runner)
    assert rows[0]["cer"] == 0.0 and rows[1]["cer"] is None


def test_scan_suffix_finds_base_reference(tmp_path, fake_runner):
    (tmp_path / "doc.txt").write_text("A page1\n\nA page2", encoding="utf-8")
    rows = compare([scanned_pdf(tmp_path / "doc-scan.pdf")], ["A"], runner=fake_runner)
    assert rows[0]["cer"] == 0.0


def test_write_report_escapes_and_lists_models(tmp_path, fake_runner):
    rows = compare([png(tmp_path / "a.png")], ["A", "B"], runner=lambda i, m: "<b>x</b> " + m)
    out = write_report(rows, tmp_path / "r.html")
    html = out.read_text(encoding="utf-8")
    assert "&lt;b&gt;" in html and "<b>x</b>" not in html and "A" in html and "B" in html


def test_report_dir_is_gitignored():
    assert subprocess.run(["git", "check-ignore", "-q", "compare-reports/x.html"]).returncode == 0
