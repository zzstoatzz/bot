"""Influence choice identity, version provenance, and complete pagination."""

import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from bot.core.influences import COLLECTION, Influence, read_influences

OWNER = "did:plc:phi"
SUBJECT = "did:plc:author"


def value(active=True):
    return {
        "subject": {
            "uri": f"at://{SUBJECT}/app.bsky.actor.profile/self",
            "cid": "bafy-profile",
        },
        "reason": "Their dialogue follows a specific disagreement.",
        "active": active,
        "selectedBy": "phi",
        "createdAt": "2026-09-05T10:00:00Z",
        "updatedAt": "2026-09-05T11:00:00Z",
    }


def test_subject_pins_identity_and_profile_version():
    choice = Influence.model_validate(value())
    assert choice.actor_did == SUBJECT
    assert choice.subject.cid == "bafy-profile"
    for bad in [
        "at://author.test/app.bsky.actor.profile/self",
        f"at://{SUBJECT}/app.bsky.feed.post/abc",
    ]:
        data = value()
        data["subject"]["uri"] = bad
        with pytest.raises(ValidationError):
            Influence.model_validate(data)


async def test_reader_keeps_retired_records_and_exact_versions_across_pages():
    calls = []

    def serve(request):
        calls.append(request)
        second = request.url.params.get("cursor") == "page2"
        data = {
            "records": [
                {
                    "uri": f"at://{OWNER}/{COLLECTION}/" + ("two" if second else "one"),
                    "cid": "bafy-two" if second else "bafy-one",
                    "value": value(not second),
                }
            ]
        }
        if not second:
            data["cursor"] = "page2"
        return httpx.Response(200, json=data)

    async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
        choices = await read_influences(client, "https://pds.test", OWNER)
    assert len(calls) == 2
    assert [c.cid for c in choices] == ["bafy-one", "bafy-two"]
    assert [c.value.active for c in choices] == [True, False]


async def test_failed_later_page_does_not_return_a_partial_choice_list():
    def serve(request):
        if request.url.params.get("cursor"):
            return httpx.Response(503)
        return httpx.Response(200, json={"records": [], "cursor": "next"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await read_influences(client, "https://pds.test", OWNER)


def test_lexicon_and_reader_require_the_same_fields():
    lexicon = json.loads(Path("lexicons/io/zzstoatzz/phi/influence.json").read_text())
    required = lexicon["defs"]["main"]["record"]["required"]
    assert set(required) == set(Influence.model_json_schema()["required"])
