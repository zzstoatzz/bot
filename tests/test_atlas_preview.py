import pytest
from starlette.staticfiles import StaticFiles
from starlette.testclient import TestClient

from bot.core.atlas import PREVIEW_DOTS, atlas_preview
from bot.ui.static import CachedStaticFiles


def _atlas(n: int) -> dict:
    return {
        "generated_at": "2026-10-07T20:08:28+00:00",
        "clusters_coarse": [{}, {}, {}],
        "points": [
            {"id": str(i), "x": float(i), "y": float(i * 2), "kind": "observation"}
            for i in range(n)
        ],
    }


def test_preview_is_a_bounded_sample_with_the_real_totals():
    preview = atlas_preview(_atlas(9712))
    assert preview["point_count"] == 9712
    assert preview["group_count"] == 3
    assert preview["generated_at"] == "2026-10-07T20:08:28+00:00"
    assert 0 < len(preview["dots"]) <= PREVIEW_DOTS


def test_preview_dots_are_normalised_and_carry_only_position_and_kind():
    dots = atlas_preview(_atlas(50))["dots"]
    assert len(dots) == 50
    assert all(len(dot) == 3 for dot in dots)
    assert min(dot[0] for dot in dots) == 0
    assert max(dot[1] for dot in dots) == 1
    assert {dot[2] for dot in dots} == {"observation"}


def test_preview_skips_points_without_coordinates():
    atlas = _atlas(3)
    atlas["points"].append({"id": "x", "kind": "note"})
    atlas["points"].append({"id": "y", "x": float("nan"), "y": 1.0})
    preview = atlas_preview(atlas)
    assert preview["point_count"] == 5
    assert len(preview["dots"]) == 3


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/_app/immutable/chunks/abc123.js", "public, max-age=31536000, immutable"),
        ("/index.html", "no-cache"),
        ("/favicon.svg", None),
    ],
)
def test_hashed_assets_are_cached_forever_and_the_shell_is_revalidated(
    tmp_path, path, expected
):
    (tmp_path / "_app/immutable/chunks").mkdir(parents=True)
    (tmp_path / "_app/immutable/chunks/abc123.js").write_text("export {}")
    (tmp_path / "index.html").write_text("<!doctype html>")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    assert issubclass(CachedStaticFiles, StaticFiles)
    client = TestClient(CachedStaticFiles(directory=str(tmp_path), html=True))
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers.get("cache-control") == expected
