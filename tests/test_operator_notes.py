"""[OPERATOR NOTES] renders titles only, and a failed refresh is never silent."""

import logging

import httpx

from bot.core import operator_notes

INDEX = """# notes.zzstoatzz.io

> nate's working notes

everything in one file: https://notes.zzstoatzz.io/llms-full.txt

## ai

- [prompt caching](https://notes.zzstoatzz.io/docs/ai/prompt-caching.md)
- [message archives](https://notes.zzstoatzz.io/docs/ai/memory/message-archives.md)

## systems

- [ownership must expire](https://notes.zzstoatzz.io/docs/systems/ownership.md)
"""


def _serve(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient
    monkeypatch.setattr(
        operator_notes.httpx,
        "AsyncClient",
        lambda **kwargs: real(transport=transport, **kwargs),
    )
    monkeypatch.setattr(operator_notes, "_block_cache", {"text": "", "fetched_at": 0.0})


def test_render_keeps_titles_by_section_and_drops_urls():
    block = operator_notes._render(INDEX)
    assert block.splitlines()[1:] == [
        "ai: prompt caching; message archives",
        "systems: ownership must expire",
    ]
    assert block.startswith("[OPERATOR NOTES")
    assert "https://notes.zzstoatzz.io/docs" not in block


def test_render_is_empty_without_titles():
    assert operator_notes._render("# notes\n\nnothing here") == ""


async def test_block_is_fetched_once_per_ttl(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request.url)
        return httpx.Response(200, text=INDEX)

    _serve(monkeypatch, handler)
    first = await operator_notes.get_operator_notes_block()
    second = await operator_notes.get_operator_notes_block()
    assert "ownership must expire" in first
    assert second == first
    assert len(calls) == 1


async def test_failed_refresh_warns_and_keeps_the_last_index(monkeypatch, caplog):
    _serve(monkeypatch, lambda request: httpx.Response(503))
    with caplog.at_level(logging.WARNING, logger="bot.operator_notes"):
        assert await operator_notes.get_operator_notes_block() == ""
    assert "operator notes index unavailable" in caplog.text

    operator_notes._block_cache.update(text="[OPERATOR NOTES] stale", fetched_at=0.0)
    assert await operator_notes.get_operator_notes_block() == "[OPERATOR NOTES] stale"
