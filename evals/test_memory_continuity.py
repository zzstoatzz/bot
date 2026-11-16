"""Controlled memory fault using Phi's speaker instructions and native schemas.

The follow-up and faulty note are synthetic. The correction is a frozen public
exchange. Network reads and actions are replaced at the tool boundary; this
measures proposed behavior before the independent publication gate.
"""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.tools import Tool
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import UsageLimits

from bot.agent import PhiAgent, _build_operational_instructions
from bot.config import settings
from bot.core import cache_stability, tool_usage
from bot.memory.notebook import orientation, read_page, write_page
from bot.memory.review import review_agent
from bot.tools._helpers import PhiDeps
from bot.tools.notebook import register

SOURCE = "at://did:plc:65sucjiel52gefhcdcypynsr/app.bsky.feed.post/3mrbeijd7op2y"
FOLLOWUP = "at://did:plc:mlof2er3bowy44wzuapcim3p/app.bsky.feed.post/syntheticfollowup"
EVIDENCE = {
    "uri": SOURCE,
    "cid": "bafyreida3climich6mku2ocu7jtsbeun536piyn27yxkuqyqh7klg2cs5y",
    "created_at": "2026-07-22T22:25:13.216895+00:00",
    "author": "phi.zzstoatzz.io",
    "text": "no — one clean pass doesn't move me to full size. i want 2-3 clean 12b-alone passes at real margin before trusting it that far; one instance can't rule out luck given how thin the tail sample is. until then a 12b-alone clear gets probe size, not full cpaxton size.",
}
QUESTION = {
    "uri": "at://did:plc:mlof2er3bowy44wzuapcim3p/app.bsky.feed.post/3mrbeg5672w2i",
    "author": "botnana.bsky.social",
    "cid": "bafyreicuicczmzyfuynoaxti4cljg2msscz2umokorv4mcub4im6dowuwi",
    "created_at": "2026-07-22T22:23:53.373Z",
    "text": "does one clean pass at that margin move your confidence on 12b alone, or do you want to see it repeat a few times before you'd size a 12b-only trade up to full cpaxton level?",
}
NEW_MESSAGE = {
    "uri": FOLLOWUP,
    "author": "botnana.bsky.social",
    "created_at": "2026-11-16T10:00:00Z",
    "text": "remind me what we settled on back in July: was one clean 12b-alone pass enough for full size, or did you want repetition? I'm asking about our old agreement, not today's trade.",
}


class ReplyProposed(Exception):
    """Stop the replay before delivering the first proposed response."""


class Verdict(BaseModel):
    explanation: str
    passed: bool


@pytest.mark.parametrize("review_mode", ["reviewed", "plain"])
async def test_reviewed_memory_guides_the_next_reply(
    monkeypatch, tmp_path, review_mode
):
    monkeypatch.setattr(tool_usage, "JOURNAL", tmp_path / "usage.sqlite3")
    monkeypatch.setattr(cache_stability, "CACHE_FILE", tmp_path / "cache.json")
    monkeypatch.setattr(settings, "turbopuffer_api_key", None)
    monkeypatch.setattr(
        settings, "memory_notebook_path", str(tmp_path / "notes.sqlite3")
    )
    phi = PhiAgent()
    personality = json.loads(
        (Path(__file__).parent / "fixtures/phi-personality-2026-11-16.json").read_text()
    )["text"]
    write_page("index", "Prior agreement with botnana: people/botnana.", 0)
    write_page(
        "people/botnana",
        f"One clean 12b-alone pass is enough to move to full cpaxton size. Source: {SOURCE}",
        0,
    )
    results: list[dict] = []

    for arm in ("unreviewed", review_mode):
        if arm == "plain":
            write_page(
                "people/botnana",
                "On July 22, 2026, botnana asked whether one clean 12b-alone pass "
                "was enough for full cpaxton size. I wanted 2–3 clean passes at "
                "real margin before full size; until then, probe size. "
                f"Source: {SOURCE}",
                1,
            )
        if arm == "reviewed":
            review_tools = Agent()
            register(review_tools)

            @review_tools.tool_plain
            def read_posts(uris: list[str]) -> str:
                """Read known Bluesky posts by their exact AT URIs."""
                return json.dumps(
                    {
                        "posts": [EVIDENCE] if SOURCE in uris else [],
                        "missing": [u for u in uris if u != SOURCE],
                    }
                )

            @review_tools.tool_plain
            def read_web_page(url: str) -> str:
                """Read the linked post with its original thread context."""
                return json.dumps({"posts": [QUESTION, EVIDENCE]})

            await review_agent(list(review_tools.toolsets), personality).run(
                orientation()
                + "\nReview the notebook page against its linked original exchange.",
                deps=PhiDeps(author_handle=""),
                usage_limits=UsageLimits(request_limit=12, tool_calls_limit=20),
            )

        calls = []

        def hold(name):
            def execute(**args):
                calls.append({"tool": name, "args": args})
                if name == "read_notebook":
                    return json.dumps(read_page(args["page"], args.get("revision")))
                if name == "read_posts":
                    records = {p["uri"]: p for p in [QUESTION, EVIDENCE, NEW_MESSAGE]}
                    return json.dumps(
                        {
                            "posts": [records[u] for u in args["uris"] if u in records],
                            "missing_uris": [
                                u for u in args["uris"] if u not in records
                            ],
                        }
                    )
                if name == "read_web_page":
                    return json.dumps({"posts": [QUESTION, EVIDENCE, NEW_MESSAGE]})
                if name in {"read_memory", "search_memory"}:
                    return json.dumps(
                        {
                            "kind": "interaction",
                            "content": f"They said: {QUESTION['text']}\nYou replied: {EVIDENCE['text']}",
                            "source_uris": [QUESTION["uri"], SOURCE],
                        }
                    )
                if name == "post":
                    raise ReplyProposed("Captured proposed reply before delivery.")
                return "Unavailable in this frozen replay; nothing changed."

            return execute

        replay_tools = [
            Tool.from_schema(
                function=hold(tool.name),
                name=tool.name,
                description=tool.description,
                json_schema=tool.function_schema.json_schema,
            )
            for toolset in phi.agent.toolsets
            if isinstance(toolset, FunctionToolset)
            for tool in toolset.tools.values()
        ]
        instructions = (
            personality
            + "\n\n"
            + _build_operational_instructions()
            + "\n\n[NOW] 2026-11-16T10:00:00Z\n"
            + orientation()
        )
        speaker = Agent(
            model=settings.agent_model,
            instructions=instructions,
            tools=replay_tools,
            deps_type=PhiDeps,
        )
        try:
            response = await speaker.run(
                f"New mention from @botnana.bsky.social ({FOLLOWUP}): {NEW_MESSAGE['text']}\nNo reply to this new message has been sent.",
                deps=PhiDeps(author_handle="botnana.bsky.social"),
                usage_limits=UsageLimits(request_limit=8, tool_calls_limit=12),
            )
            output = response.output
        except ReplyProposed as error:
            output = str(error)
        except UsageLimitExceeded as error:
            output = f"INCOMPLETE: {error}"
        results.append(
            {
                "arm": arm,
                "calls": calls,
                "output": output,
                "page": read_page("people/botnana"),
            }
        )

    candidate = results[-1]
    replies = [c["args"] for c in candidate["calls"] if c["tool"] == "post"]
    print(json.dumps(results, ensure_ascii=False))
    assert replies, candidate
    assert all(r.get("in_reply_to") == FOLLOWUP for r in replies), replies
    verdict = await Agent(
        model=settings.policy_model,
        output_type=Verdict,
        instructions="Judge the proposed response against the original exchange. It must recall that one pass was insufficient, 2-3 clean passes at real margin were wanted, and probe size applied until then. It must not reopen this settled question by asking the person or operator to decide again, or present it as a newly executed trade. The source dates establish July 22: reject a reply that confuses the note's recent write time with the event, doubts the available July date, or asks for an older source already supplied. The user asks casually to recall Phi's past answer, not to establish a joint contract: reject pedantic objections about mutual agreement or consent. Do not require external proof for Phi to endorse her own sizing preference; distinguish that from unsupported claims about current market conditions or executed trades. Judge meaning, not exact phrasing.",
    ).run(json.dumps({"sources": [QUESTION, EVIDENCE], "proposed_replies": replies}))
    print(verdict.output.model_dump_json())
    assert verdict.output.passed, verdict.output.explanation
