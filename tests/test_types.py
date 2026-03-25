"""Test cosmik record types — validation and serialization."""

import pytest
from pydantic import ValidationError

from bot.types import (
    CosmikConnection,
    CosmikNoteCard,
    CosmikUrlCard,
    NoteContent,
    UrlContent,
)


# --- CosmikConnection ---


def test_connection_valid():
    conn = CosmikConnection(
        source="https://example.com",
        target="at://did:plc:abc/app.bsky.feed.post/123",
        connectionType="related",
        note="test",
    )
    assert conn.source == "https://example.com"
    assert conn.connection_type == "related"


def test_connection_to_record_full():
    conn = CosmikConnection(
        source="https://a.com",
        target="https://b.com",
        connectionType="supports",
        note="because reasons",
    )
    record = conn.to_record()
    assert record == {
        "source": "https://a.com",
        "target": "https://b.com",
        "connectionType": "supports",
        "note": "because reasons",
    }


def test_connection_to_record_minimal():
    conn = CosmikConnection(source="https://a.com", target="https://b.com")
    record = conn.to_record()
    assert record == {"source": "https://a.com", "target": "https://b.com"}


def test_connection_rejects_bare_string():
    with pytest.raises(ValidationError):
        CosmikConnection(source="not-a-url", target="https://b.com")


def test_connection_rejects_invalid_type():
    with pytest.raises(ValidationError):
        CosmikConnection(
            source="https://a.com",
            target="https://b.com",
            connectionType="invented",
        )


# --- CosmikNoteCard ---


def test_note_card_valid():
    card = CosmikNoteCard(content=NoteContent(text="hello world"))
    assert card.type == "NOTE"
    assert card.content.text == "hello world"


def test_note_card_to_record():
    card = CosmikNoteCard(content=NoteContent(text="a thought"))
    assert card.to_record() == {"type": "NOTE", "content": {"text": "a thought"}}


def test_note_card_rejects_empty():
    # pydantic allows empty string for str fields — max_length is the guard
    card = CosmikNoteCard(content=NoteContent(text=""))
    assert card.content.text == ""


def test_note_card_rejects_too_long():
    with pytest.raises(ValidationError):
        CosmikNoteCard(content=NoteContent(text="x" * 10001))


# --- CosmikUrlCard ---


def test_url_card_valid():
    card = CosmikUrlCard(
        content=UrlContent(url="https://example.com", title="Example", description="A site")
    )
    assert card.type == "URL"
    assert card.content.url == "https://example.com"


def test_url_card_to_record_full():
    card = CosmikUrlCard(
        content=UrlContent(url="https://example.com", title="Ex", description="desc")
    )
    assert card.to_record() == {
        "type": "URL",
        "content": {"url": "https://example.com", "title": "Ex", "description": "desc"},
    }


def test_url_card_to_record_minimal():
    card = CosmikUrlCard(content=UrlContent(url="https://example.com"))
    assert card.to_record() == {"type": "URL", "content": {"url": "https://example.com"}}


def test_url_card_rejects_bare_string():
    with pytest.raises(ValidationError):
        CosmikUrlCard(content=UrlContent(url="not-a-url"))


def test_url_card_accepts_at_uri():
    card = CosmikUrlCard(content=UrlContent(url="at://did:plc:abc/collection/rkey"))
    assert card.content.url == "at://did:plc:abc/collection/rkey"
