import os
import time

from bot.core import generated_images


def test_cache_retains_current_write_despite_existing_timestamps(monkeypatch, tmp_path):
    monkeypatch.setattr(generated_images, "cache_directory", lambda: tmp_path)
    monkeypatch.setattr(generated_images, "MAX_FILES", 2)
    future = time.time_ns() + 60_000_000_000
    for cid in ("baaa", "baab"):
        generated_images.remember_image(cid, b"older")
        os.utime(tmp_path / f"{cid}.blob", ns=(future, future))

    generated_images.remember_image("baac", b"current")

    assert len(list(tmp_path.glob("*.blob"))) == 2
    assert generated_images.recalled_image("baac") == b"current"
