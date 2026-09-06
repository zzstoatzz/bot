from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock, patch

import pytest
from atproto_client.models.dot_dict import DotDict
from pydantic_ai import RunContext

from bot.agent import memoize_per_run
from bot.core.personality import read_personality, write_personality
from bot.tools import personality
from bot.tools._helpers import PhiDeps


def client_with(records):
    repo = SimpleNamespace(
        list_records=Mock(return_value=SimpleNamespace(records=records)),
        create_record=Mock(return_value=SimpleNamespace(uri="at://phi/revision/new")),
    )
    client = SimpleNamespace(
        authenticate=AsyncMock(),
        client=SimpleNamespace(
            me=SimpleNamespace(did="did:plc:test"),
            com=SimpleNamespace(atproto=SimpleNamespace(repo=repo)),
        ),
    )
    return client, repo


def revision(text):
    return SimpleNamespace(value=DotDict({"text": text}))


async def test_latest_revision_replaces_seed_and_empty_collection_uses_seed():
    client, repo = client_with([])
    assert await read_personality(client, "seed") == "seed"
    repo.list_records.return_value.records = [revision("authored")]
    assert await read_personality(client, "seed") == "authored"
    assert repo.list_records.call_args.kwargs["params"]["reverse"] is True


async def test_failure_or_invalid_revision_does_not_silently_restore_seed():
    client, repo = client_with([revision("")])
    with pytest.raises(ValueError):
        await read_personality(client, "seed")
    repo.list_records.side_effect = RuntimeError("PDS unavailable")
    with pytest.raises(RuntimeError):
        await read_personality(client, "seed")


async def test_replacement_appends_without_overwriting_prior_revisions():
    client, repo = client_with([])
    await write_personality(client, "first", "try")
    await write_personality(client, "second", "revise")
    records = [call.kwargs["data"] for call in repo.create_record.call_args_list]
    assert [r["record"]["text"] for r in records] == ["first", "second"]
    assert all("rkey" not in r for r in records)


async def test_version_is_fixed_within_run_and_changes_next_run():
    client, repo = client_with([revision("first")])

    async def instructions():
        return await read_personality(client, "seed")

    render = memoize_per_run(instructions)
    ctx = cast(RunContext[PhiDeps], SimpleNamespace(deps=PhiDeps(author_handle="")))
    assert await render(ctx) == "first"
    repo.list_records.return_value.records = [revision("second")]
    assert await render(ctx) == "first"
    assert (
        await render(
            cast(RunContext[PhiDeps], SimpleNamespace(deps=PhiDeps(author_handle="")))
        )
        == "second"
    )


@pytest.mark.parametrize("paused", [True, False])
async def test_direct_tool_needs_no_owner_like_but_respects_pause(paused):
    registered = {}
    personality.register(
        SimpleNamespace(tool=lambda fn: registered.setdefault(fn.__name__, fn))
    )
    with (
        patch.object(
            personality,
            "get_override",
            AsyncMock(return_value={"active": paused, "message": "paused"}),
        ),
        patch.object(
            personality,
            "save_personality",
            AsyncMock(return_value="at://phi/revision/new"),
        ) as save,
    ):
        result = await registered["write_personality"](
            SimpleNamespace(deps=PhiDeps(author_handle="")),
            "new disposition",
            "experiment",
        )
        assert save.await_count == (0 if paused else 1)
        assert ("next run" in result) is not paused


def test_tool_registers_with_real_pydantic_agent():
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel

    agent = Agent(TestModel(), deps_type=PhiDeps)
    personality.register(agent)
    assert "write_personality" in agent._function_toolset.tools
