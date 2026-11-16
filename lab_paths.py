"""Path rules for web_ui.py: requests may only touch files inside benchmark_data/.

Kept free of heavy imports (torch, OCR) so tests can import it.
"""
import re
from pathlib import Path

SAMPLES_DIR = Path("benchmark_data")
_DRIVE = re.compile(r"^[A-Za-z]:")
_BAD_CHARS = re.compile(r'[\x00-\x1f<>:"|?*]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_sample(name: str, root: Path = SAMPLES_DIR) -> Path | None:
    """root/name if name is a plain file name of an existing file inside root, else None."""
    if not name or name in (".", "..") or "/" in name or "\\" in name or _DRIVE.match(name):
        return None
    path = root / name
    return path if _inside(path, root) and path.is_file() else None


def resolve_batch_dir(directory: str, root: Path = SAMPLES_DIR) -> Path | None:
    """The resolved folder if it is root or inside root, else None."""
    path = Path(directory)
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    return path if _inside(path, root) and path.is_dir() else None


def safe_upload_name(filename: str) -> str:
    """Last path part of an uploaded file name; browsers may send folders, but they must not reach the disk path."""
    name = re.split(r"[/\\]", filename or "")[-1]
    name = _DRIVE.sub("", name)
    # Names the OS cannot open (NUL, reserved devices, too long) would otherwise fail later as a 500.
    if (name in ("", ".", "..") or _BAD_CHARS.search(name) or name[-1] in ". " or len(name) > 200
            or name.split(".")[0].upper() in _RESERVED):
        raise ValueError("Invalid upload file name")
    return name
