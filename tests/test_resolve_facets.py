"""Regression tests for resolve_facet_links — ensures phi sees full URLs from facets."""

from types import SimpleNamespace

from bot.utils.thread import resolve_facet_links


def _make_record(text, facets=None):
    return SimpleNamespace(text=text, facets=facets)


def _make_facet(byte_start, byte_end, uri):
    return SimpleNamespace(
        index=SimpleNamespace(byte_start=byte_start, byte_end=byte_end),
        features=[SimpleNamespace(py_type="app.bsky.richtext.facet#link", uri=uri)],
    )


def test_no_facets():
    record = _make_record("hello world")
    assert resolve_facet_links(record) == "hello world"


def test_none_facets():
    record = _make_record("hello world", facets=None)
    assert resolve_facet_links(record) == "hello world"


def test_truncated_url_replaced():
    """The exact bug from trace 019d5004 — bluesky truncated the URL in display text."""
    text = (
        "cool. onto something else\n\n"
        "can you read this: www.letta.com/blog/context...\n\n"
        "and tell me whether there's anything interesting as far as your M.O.?"
    )
    # byte offsets for "www.letta.com/blog/context..." in the text
    encoded = text.encode("utf-8")
    start = encoded.index(b"www.letta.com/blog/context...")
    end = start + len(b"www.letta.com/blog/context...")

    record = _make_record(
        text,
        facets=[
            _make_facet(start, end, "https://www.letta.com/blog/context-constitution")
        ],
    )

    result = resolve_facet_links(record)
    assert "https://www.letta.com/blog/context-constitution" in result
    assert "context..." not in result


def test_multiple_links():
    text = "check out link1... and link2..."
    encoded = text.encode("utf-8")
    s1 = encoded.index(b"link1...")
    e1 = s1 + len(b"link1...")
    s2 = encoded.index(b"link2...")
    e2 = s2 + len(b"link2...")

    record = _make_record(
        text,
        facets=[
            _make_facet(s1, e1, "https://example.com/link1-full"),
            _make_facet(s2, e2, "https://example.com/link2-full"),
        ],
    )

    result = resolve_facet_links(record)
    assert "https://example.com/link1-full" in result
    assert "https://example.com/link2-full" in result
    assert "link1..." not in result
    assert "link2..." not in result


def test_mention_facet_ignored():
    """Mention facets should not affect the text."""
    text = "hey @someone check this"
    record = _make_record(
        text,
        facets=[
            SimpleNamespace(
                index=SimpleNamespace(byte_start=4, byte_end=12),
                features=[
                    SimpleNamespace(
                        py_type="app.bsky.richtext.facet#mention",
                        did="did:plc:abc",
                    )
                ],
            )
        ],
    )
    assert resolve_facet_links(record) == text


def test_unicode_text_byte_offsets():
    """Facet byte offsets are in UTF-8 bytes, not characters."""
    # emoji is 4 bytes in UTF-8
    text = "\U0001f600 see link..."
    encoded = text.encode("utf-8")
    start = encoded.index(b"link...")
    end = start + len(b"link...")

    record = _make_record(
        text,
        facets=[_make_facet(start, end, "https://example.com/full-link")],
    )

    result = resolve_facet_links(record)
    assert "https://example.com/full-link" in result
    assert "link..." not in result
    assert result.startswith("\U0001f600")
