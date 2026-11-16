import pytest

from lab_paths import SAMPLES_DIR, resolve_batch_dir, resolve_sample, safe_upload_name


@pytest.fixture
def root(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF")
    (tmp_path / "sub").mkdir()
    return tmp_path


def test_known_samples_resolve():
    assert resolve_sample("english_resume.pdf") is not None and resolve_sample("thai_resume.pdf") is not None


def test_sample_traversal_rejected(root):
    for name in ["../x.pdf", "sub/../../x", "..", ".", "", "sub"]:
        assert resolve_sample(name, root) is None, name


def test_windows_paths_rejected(root):
    for name in [r"..\x.pdf", r"C:\Windows\win.ini", "C:a.pdf", "/etc/passwd", r"\\server\share"]:
        assert resolve_sample(name, root) is None, name


def test_missing_sample_is_none(root):
    assert resolve_sample("nope.pdf", root) is None
    assert resolve_sample("a.pdf", root) == root / "a.pdf"


def test_default_batch_dir_allowed():
    assert resolve_batch_dir(str(SAMPLES_DIR)) is not None


def test_batch_outside_root_rejected(root):
    assert resolve_batch_dir(str(root.parent), root) is None
    assert resolve_batch_dir("C:\\", root) is None
    assert resolve_batch_dir(str(root / "sub" / ".." / ".."), root) is None
    assert resolve_batch_dir(str(root / "sub"), root) == (root / "sub").resolve()
    assert resolve_batch_dir(str(root / "a.pdf"), root) is None  # a file, not a folder


def test_upload_name_keeps_basename():
    assert safe_upload_name("a/b/cv.pdf") == "cv.pdf"
    assert safe_upload_name(r"..\..\cv.pdf") == "cv.pdf"
    assert safe_upload_name(r"C:\Users\x\cv.pdf") == "cv.pdf"
    assert safe_upload_name("C:cv.pdf") == "cv.pdf"


def test_upload_name_rejects_empty():
    for name in ["", "a/", "..", "x/..", "."]:
        with pytest.raises(ValueError):
            safe_upload_name(name)
