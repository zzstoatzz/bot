"""Keep uploaded image bytes until the PDS can serve the referenced blob."""

import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from bot.config import settings

MAX_BYTES = 1_000_000
MAX_FILES = 64


def cache_directory() -> Path:
    return Path(settings.ops_log_path).parent / "generated-images"


def _path(cid: str) -> Path:
    if not re.fullmatch(r"b[a-z2-7]+", cid):
        raise ValueError("expected a base32 blob CID")
    return cache_directory() / (cid + ".blob")


def remember_image(cid: str, data: bytes) -> None:
    """Persist the exact uploaded bytes, bounded to the latest 64 images."""
    if not 0 < len(data) <= MAX_BYTES:
        raise ValueError("generated image exceeds cache limit")
    target = _path(cid)
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=target.parent, delete=False) as temp:
        staging = Path(temp.name)
        temp.write(data)
    try:
        staging.replace(target)
    finally:
        staging.unlink(missing_ok=True)
    entries = sorted(target.parent.glob("*.blob"), key=lambda p: p.stat().st_mtime)
    for old in entries[:-MAX_FILES]:
        old.unlink(missing_ok=True)


def recalled_image(cid: str) -> bytes | None:
    """No PDS read is needed for a still-unreferenced generated image."""
    path = _path(cid)
    try:
        with path.open("rb") as source:
            data = source.read(MAX_BYTES + 1)
    except FileNotFoundError:
        return None
    if not 0 < len(data) <= MAX_BYTES:
        raise ValueError("invalid cached image size")
    return data
