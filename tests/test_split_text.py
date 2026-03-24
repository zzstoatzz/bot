"""Regression tests for post splitting (grapheme limit 300)."""

from bot.core.atproto_client import _split_text


def test_short_text_unchanged():
    assert _split_text("hello world") == ["hello world"]


def test_exactly_300_unchanged():
    text = "a" * 300
    assert _split_text(text) == [text]


def test_splits_at_sentence_boundary():
    # Two sentences, second pushes past 300
    first = "a" * 250 + "."
    second = " " + "b" * 100
    text = first + second
    chunks = _split_text(text)
    assert len(chunks) == 2
    assert chunks[0] == first
    assert chunks[1] == "b" * 100


def test_splits_at_word_boundary():
    # No sentence boundaries, should split at last space
    text = " ".join(["word"] * 100)  # 499 chars
    chunks = _split_text(text)
    assert all(len(c) <= 300 for c in chunks)
    assert " ".join(chunks) == text


def test_splits_at_paragraph_break():
    first = "a" * 200 + "\n"
    second = "b" * 200
    text = first + second
    chunks = _split_text(text)
    assert len(chunks) == 2
    assert chunks[0] == "a" * 200
    assert chunks[1] == "b" * 200


def test_three_way_split():
    text = ". ".join(["x" * 280] * 3)
    chunks = _split_text(text)
    assert len(chunks) == 3
    assert all(len(c) <= 300 for c in chunks)


def test_hard_break_no_spaces():
    text = "a" * 600
    chunks = _split_text(text)
    assert len(chunks) == 2
    assert chunks[0] == "a" * 300
    assert chunks[1] == "a" * 300
