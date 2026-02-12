"""Tests for rich text URL parsing, including bare domain URLs."""

from bot.core.rich_text import parse_urls


def test_full_url():
    facets = parse_urls("check out https://example.com/path")
    assert len(facets) == 1
    assert facets[0]["features"][0]["uri"] == "https://example.com/path"


def test_bare_domain_url():
    facets = parse_urls("check out cnbc.com/2025/markets")
    assert len(facets) == 1
    assert facets[0]["features"][0]["uri"] == "https://cnbc.com/2025/markets"


def test_bare_domain_no_path():
    facets = parse_urls("visit example.com")
    assert len(facets) == 1
    assert facets[0]["features"][0]["uri"] == "https://example.com"


def test_full_url_not_duplicated():
    """Full https:// URL should produce exactly one facet, not a bare URL duplicate."""
    facets = parse_urls("see https://cnbc.com/path for details")
    assert len(facets) == 1
    assert facets[0]["features"][0]["uri"] == "https://cnbc.com/path"


def test_mixed_full_and_bare():
    facets = parse_urls("https://a.com and also b.org/page")
    assert len(facets) == 2
    uris = {f["features"][0]["uri"] for f in facets}
    assert uris == {"https://a.com", "https://b.org/page"}


def test_byte_positions_bare_url():
    text = "see cnbc.com/path ok"
    facets = parse_urls(text)
    assert len(facets) == 1
    start = facets[0]["index"]["byteStart"]
    end = facets[0]["index"]["byteEnd"]
    assert text.encode("UTF-8")[start:end] == b"cnbc.com/path"
