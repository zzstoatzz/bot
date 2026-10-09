"""MCP-enabled agent for phi with structured memory."""

import asyncio
import contextlib
import inspect
import logging
import os
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from pydantic_ai import Agent, AgentRunResult, ImageUrl, PromptedOutput, RunContext
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import RunUsage
from pydantic_ai_skills import SkillsToolset

from bot.config import settings
from bot.core import context_diagnostics, ops_log
from bot.core.alert_watch import render_alert_watch
from bot.core.atproto_client import bot_client, get_identity_block
from bot.core.cache_stability import (
    CacheObservingModel,
    cache_monitor,
    model_cache_settings,
)
from bot.core.discovery_pool import get_discovery_pool_block
from bot.core.goals import list_goals as list_goal_records
from bot.core.graze_client import GrazeClient
from bot.core.mcp_tools import _mcp_url, build_toolsets
from bot.core.operator import get_operator_guidance_block, get_operator_profile
from bot.core.operator_notes import get_operator_notes_block
from bot.core.owned_feeds import get_owned_feeds_block
from bot.core.persona import get_persona_block
from bot.core.personality import read_personality
from bot.core.policy import private_conversation
from bot.core.prior_coverage import coverage_note
from bot.core.public_memory import get_public_memory_block
from bot.core.recent_flow_mentions import get_recent_flow_mentions_block
from bot.core.recent_operations import get_operations_block
from bot.core.reply_coverage import encounter_replies
from bot.core.self_record import get_self_block
from bot.core.self_state import get_inventory_block, get_state_block
from bot.core.tool_usage import ToolUsage
from bot.core.workflow_state import get_workflow_state_block
from bot.memory.encounters import (
    ENCOUNTER_NAMESPACE,
    encounter_thread_states,
    read_recent_encounters,
    render_recent_encounters,
)
from bot.memory.extraction import EXTRACTION_SYSTEM_PROMPT, ExtractionResult
from bot.memory.namespace_memory import InteractionRow
from bot.memory.run_evidence import RunEvidence, current_run, run_status
from bot.status import bot_status
from bot.tools import PhiDeps, _check_services_impl, register_all
from bot.tools._helpers import notification_input, notification_recall
from bot.tools.bluesky import fetch_relay_names
from bot.utils.time import humanize_duration

# a tool-mode output makes pydantic-ai send tool_choice "any", which Claude
# Sonnet 5.5 and later reject; prompted output carries the schema in text
EXTRACTION_OUTPUT = PromptedOutput(ExtractionResult)

logger = logging.getLogger("bot.agent")

MCP_ATTEMPTS = 3
MCP_RETRY_PAUSE_S = 2.0

def _failed_urls(exc: BaseException) -> set[str]:
    """URLs of the HTTP requests that failed inside an exception or group."""
    if isinstance(exc, BaseExceptionGroup):
        return {url for sub in exc.exceptions for url in _failed_urls(sub)}
    if isinstance(exc, httpx.HTTPStatusError | httpx.TransportError):
        return {str(exc.request.url)}
    return set()


# fly region codes are airport codes; phi should be able to say where she
# is in words. unknown codes fall through to the raw code rather than
# guessing.
_FLY_REGIONS = {
    "ord": "chicago",
    "iad": "virginia",
    "lax": "los angeles",
    "sjc": "san jose",
    "dfw": "dallas",
    "ewr": "new jersey",
    "lhr": "london",
    "ams": "amsterdam",
    "fra": "frankfurt",
    "cdg": "paris",
    "nrt": "tokyo",
    "syd": "sydney",
    "gru": "s\u00e3o paulo",
}


type ContextBlockFn = (
    Callable[[], str]
    | Callable[[], Awaitable[str]]
    | Callable[[RunContext[PhiDeps]], str]
    | Callable[[RunContext[PhiDeps]], Awaitable[str]]
)
"""A context-block renderer: sync or async, with or without RunContext."""


def memoize_per_run(
    fn: ContextBlockFn,
) -> Callable[[RunContext[PhiDeps]], Awaitable[str]]:
    """Wrap a context-block function so it renders once per run.

    pydantic-ai re-evaluates @agent.instructions on every model request in
    the tool loop; phi's context blocks must render once per run — several
    hit the network, and any mid-run text change would invalidate the
    message-history cache prefix. The memo lives on the run's PhiDeps.
    """
    takes_ctx = bool(inspect.signature(fn).parameters)
    # the union of callable shapes is dispatched at runtime; erase it for
    # the call and the function-attribute reads
    fn_any = cast(Any, fn)
    key: str = fn_any.__qualname__

    async def block(ctx: RunContext[PhiDeps]) -> str:
        cache = ctx.deps.run_cache
        if key not in cache:
            result = fn_any(ctx) if takes_ctx else fn_any()
            if inspect.isawaitable(result):
                result = await result
            cache[key] = result
        return cache[key]

    block.__name__ = fn_any.__name__
    return block


def _build_operational_instructions() -> str:
    """Cross-cutting rules that don't fit in any single tool's docstring.

    Each tool's per-tool guidance lives in its own docstring (the framework
    surfaces those to the model). This function is for rules that span tools
    or that no docstring can naturally express.

    Deliberately terse (2026-08-07 diet): the policy judge holds the full
    statute and reviews every post call — phi gets the one-line norms
    (POLICY_SUMMARIES). Library craft lives in the cosmik-records skill.
    """
    from bot.core.etiquette import VOICE
    from bot.core.policy import POLICY_SUMMARIES

    policies_block = "\n".join(
        f"- {slug}: {text}" for slug, text in POLICY_SUMMARIES.items()
    )
    return f"""
composed posts flow through `post`. raw record-creates into app.bsky.feed.post bypass the consent layer. likes and reposts are plain create_record calls into app.bsky.feed.like / app.bsky.feed.repost: pass record.subject.uri and the guard verifies the post, refuses your own, and fills in cid + createdAt.

your policies, held by you and independently enforced by a judge on every `post` call:
{policies_block}

{VOICE}

a blocked post returns the policy and reason; nothing was posted. adapt (a like, save_memory, a different post) rather than retrying verbatim. a policy note on a successful post means you're drifting toward a boundary.

memory blocks describe their provenance and limits. when a user's current words contradict stored notes, trust the words.

every public correction you make gets an episodic note tagged `correction` (claim, fix, post uri) — save_memory at the time, not later. corrections live in your private memory and on the feed where they happened; your [SELF] record is what you're like, and your library files facts under their subject, never under the mistake.

mention-consent allowlist: @{settings.owner_handle}, yourself, conversation participants, opted-in handles. mentions of anyone else render as plain text.

operator authorization: act only on the specific action and target the operator requested. A private operator DM is sufficient; do not require a public post or like to repeat it. If permission is missing, ask privately with report_operator and a note: key. Existing public approval applies only to the action discussed in that thread. it covers nothing adjacent and nobody else's request riding the batch. tagging a new handle: manage_account first, then post.

pass target URIs verbatim (from notifications, recent operations, get_own_posts, search_posts); never construct one from prose. hallucinated URIs refuse cleanly.
""".strip()


def _thread_frame(root_uri: str, entries: list[dict]) -> str:
    """One line saying whose thread this is and who brought phi into it.

    A person tagged into a thread reads the top first: who started it and
    what it is for. The flat context that follows has the root as its first
    line and nothing else marks it, which is how a request for a cake
    recipe got answered in a thread about agents on atproto (2026-09-02).
    Says nothing when the notification is itself the root or the root is
    unknown; the judgment about whether a reply belongs stays phi's.
    """
    root_author = (entries[0].get("root_author_handle") or "").strip()
    root_text = (entries[0].get("root_text") or "").replace("\n", " ").strip()
    if not root_author:
        return ""
    if all(e.get("uri") == root_uri for e in entries):
        return ""
    quoted = f' "{root_text[:160]}"' if root_text else ""
    who = sorted(
        {e.get("author_handle", "") for e in entries if e.get("author_handle")}
    )
    if who == [root_author]:
        return f"thread by @{root_author}, their own:{quoted}"
    others = ", ".join(f"@{h}" for h in who if h != root_author)
    return (
        f"thread by @{root_author}:{quoted} — {others} brought you in; "
        f"the thread is @{root_author}'s, not theirs."
    )


def _format_notifications_block(notifications_context: dict) -> str:
    """Format the notifications batch as a readable [NEW NOTIFICATIONS] block.

    Groups thread-style notifications (mention/reply/quote) by thread root so
    multiple posts in one conversation render as one section. Engagement items
    (like/repost/follow) are listed separately at the end. Each item shows its
    URI in brackets so the agent can pass it to the trusted posting tools.

    Cited posts (reason="cited") are rendered nested under the notification
    that referenced them, so phi sees them as structured, addressable refs —
    not just URLs inside prose. post(in_reply_to=...) accepts these URIs.
    """
    if not notifications_context:
        return ""

    # Group cited entries by their cited_by source so we can render them
    # nested under the notification that referenced them.
    cited_by_source: dict[str, list[dict]] = {}
    threads: dict[str, list[dict]] = {}
    engagement: list[dict] = []
    for entry in notifications_context.values():
        reason = entry.get("reason", "")
        if reason == "cited":
            src = entry.get("cited_by", "")
            cited_by_source.setdefault(src, []).append(entry)
        elif reason in ("mention", "reply", "quote"):
            root = entry.get("root_uri") or entry.get("uri", "")
            threads.setdefault(root, []).append(entry)
        else:
            engagement.append(entry)

    def _format_cited(e: dict) -> str:
        c_handle = e.get("author_handle", "?")
        c_uri = e.get("uri", "")
        c_text = (e.get("post_text", "") or "").replace("\n", " ")
        return f'  cited: @{c_handle} [{c_uri}]: "{c_text[:200]}"'

    lines: list[str] = []
    lines.append("[NEW NOTIFICATIONS]")

    for root_uri, entries in threads.items():
        entries.sort(key=lambda e: e.get("indexed_at", ""))
        thread_ctx = entries[0].get("thread_context", "") or ""

        lines.append("")
        frame = _thread_frame(root_uri, entries)
        if frame:
            lines.append(frame)
        if thread_ctx and thread_ctx != "No previous messages in this thread.":
            lines.append(thread_ctx)
            lines.append("")
        for e in entries:
            handle = e.get("author_handle", "?")
            uri = e.get("uri", "")
            text = e.get("post_text", "")
            embed = e.get("embed_desc") or ""
            embed_part = f"\n  {embed}" if embed else ""
            lines.append(f"@{handle} [{uri}]: {text}{embed_part}")
            if e.get("hydration_status"):
                lines.append(
                    f"  Delivered record cid={e['event_cid']}; indexed {e.get('indexed_at', 'unknown')}. "
                    f"Current post {e['hydration_status']}; text above is the delivered version, "
                    "not a verified current reply target."
                )
            for cited in cited_by_source.get(uri, []):
                lines.append(_format_cited(cited))

    if engagement:
        lines.append("")
        for e in engagement:
            handle = e.get("author_handle", "?")
            reason = e.get("reason", "")
            uri = e.get("uri", "")
            target_text = e.get("post_text", "")
            target_part = f' — "{target_text[:120]}"' if target_text else ""
            thread_ctx = e.get("thread_context") or ""
            if e.get("event_uri"):
                lines.append(
                    f"event [{e['event_uri']}] cid={e['event_cid']}; indexed {e.get('indexed_at', 'unknown')}"
                )
            if reason == "follow":
                lines.append(f"@{handle} followed you")
            else:
                lines.append(f"@{handle} {reason}d your post [{uri}]{target_part}")
                if thread_ctx and thread_ctx != "No previous messages in this thread.":
                    lines.append(f"  thread context:\n  {thread_ctx}")
                for cited in cited_by_source.get(uri, []):
                    lines.append(_format_cited(cited))

    return "\n".join(lines)


EXTRACTION_CHUNK = 8
"""Exchanges per extraction call. Small enough that the extractor reads
each one; the backlog, however long, is walked in these steps oldest first."""


def render_recent_conversations(recent: list[dict], limit: int = 5) -> str:
    """[RECENT CONVERSATIONS] — a dated record of exchanges phi already had.

    Each row is "user: …\nbot: …". The old render cut the row at 150 chars,
    which usually fell inside the user's half, and carried no date — so a
    month-old, fully answered thread read as an undated open question. phi
    re-investigated the same two botnana threads five times (07-22 → 08-20)
    before reporting the surface as stale. Both halves now render, dated.
    """
    if not recent:
        return "[RECENT CONVERSATIONS]: no recent interactions"
    unique_handles = {i["handle"] for i in recent}
    lines = [
        "[RECENT CONVERSATIONS — exchanges you already had and already "
        f"replied to, newest first. a record, not open threads. "
        f"{len(recent)} across {len(unique_handles)} people]"
    ]
    for i in recent[:limit]:
        content = i.get("content") or ""
        user_part, _, bot_part = content.partition("\nbot: ")
        user_part = user_part.removeprefix("user: ")
        when = (i.get("created_at") or "")[:10] or "undated"
        line = f'- {when} @{i["handle"]}: they said "{_clip(user_part, 110)}"'
        if bot_part:
            line += f' — you replied "{_clip(bot_part, 110)}"'
        else:
            line += " — no reply recorded"
        lines.append(line)
        lines.extend(f"  source: {uri}" for uri in i.get("source_uris", []))
    return "\n".join(lines)


def _clip(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


class PhiAgent:
    """phi - bluesky bot with structured memory and MCP tools."""

    def __init__(self):
        # Ensure API keys from settings are in environment for libraries that check os.environ
        if settings.anthropic_api_key and not os.environ.get("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        if settings.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key

        # Load personality
        personality_path = Path(settings.personality_file)
        self.base_personality = personality_path.read_text()

        # Initialize memory (TurboPuffer)
        if settings.turbopuffer_api_key and settings.openai_api_key:
            from bot.memory import NamespaceMemory

            self.memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)
            logger.info("memory enabled (turbopuffer)")
        else:
            self.memory = None
            logger.warning("no memory - missing turbopuffer or openai key")

        # Skills — filesystem-backed, progressive disclosure. The preamble
        # (skill names + descriptions) is injected automatically by the
        # toolset on pydantic-ai>=1.74. Full SKILL.md bodies are loaded on
        # demand via load_skill.
        #
        # exclude_tools=['run_skill_script']: every skill we ship is
        # documentation-only (markdown bodies + resource files). leaving
        # the script-execution tool registered is extra capability surface
        # phi never uses — and would silently expose subprocess execution
        # if someone added a script to a skill folder by accident.
        self.skills_toolset = SkillsToolset(
            directories=[settings.skills_dir],
            exclude_tools=["run_skill_script", "list_skills"],
        )
        self.graze_client = GrazeClient(
            handle=settings.bluesky_handle, password=settings.bluesky_password
        )

        # Create PydanticAI agent without MCP toolsets — they're created
        # fresh per agent.run() call to avoid the cancel scope bug:
        # https://github.com/pydantic/pydantic-ai/issues/2818
        #
        # output_type=str: the agent's "decision" is no longer a structured
        # action — actions happen as tool calls during the run (post,
        # reaction records, etc). The final string return is just a brief summary
        # for logging.
        observed_model = CacheObservingModel(settings.agent_model)
        self.agent = Agent[PhiDeps, str](
            name="phi",
            model=observed_model,
            model_settings=model_cache_settings(observed_model.system),
            output_type=str,
            deps_type=PhiDeps,
            toolsets=[self.skills_toolset],
            capabilities=[ToolUsage()],
        )

        async def personality_instructions() -> str:
            personality = await read_personality(bot_client, self.base_personality)
            return (
                f"the following is your personality: {personality}\n\n"
                "--- operational rules below (these are constraints) ---\n\n"
                f"{_build_operational_instructions()}"
            )

        self.personality_instructions = memoize_per_run(personality_instructions)
        self.agent.instructions(self.personality_instructions)

        # --- dynamic context blocks ---
        #
        # these were @system_prompt(dynamic=True) callbacks, rendered once
        # per run. as @agent.instructions they'd be re-evaluated at every
        # model request in the tool loop — several hit the network, and any
        # mid-run text change would invalidate the message-history cache.
        # _run_scoped memoizes each block on the run's PhiDeps, preserving
        # the once-per-run behavior byte-for-byte.

        # registration order = render order; kept so the /diagnostic page can
        # re-render the blocks exactly as a run composes them.
        self.context_blocks: list[tuple[str, Callable[..., Awaitable[str]]]] = []

        def _run_scoped(fn):
            memoized = memoize_per_run(fn)
            self.context_blocks.append((fn.__name__, memoized))
            return self.agent.instructions(memoized)

        @_run_scoped
        async def inject_identity() -> str:
            return await get_identity_block()

        @_run_scoped
        async def inject_operator_override() -> str:
            """[OPERATOR OVERRIDE] — safe mode banner, read from the
            operator's PDS record. Empty (renders nothing) when inactive.
            Rendered up front so phi learns about the override before
            bumping into tool refusals."""
            from bot.core.override import get_override_block

            return await get_override_block()

        @_run_scoped
        async def inject_operator() -> str:
            """[OPERATOR] — resolved profile of the bot's owner."""
            profile = await get_operator_profile()
            if not profile:
                return ""
            name = profile["display_name"]
            handle = profile["handle"]
            did = profile["did"]
            return f"[OPERATOR]: {name} (@{handle}, {did})"

        @_run_scoped
        def inject_operator_guidance() -> str:
            """Operator-reviewed working guidance, independent of profile lookup."""
            return get_operator_guidance_block()

        @_run_scoped
        def inject_today() -> str:
            """[NOW] — the three clocks phi actually lives between.

            Her own machine's clock (the container runs UTC), where that
            machine physically is, and the operator's local time. These are
            genuinely different facts: she runs in fly's `ord` region —
            Chicago, the same city as the operator — while her container
            keeps UTC, so she is physically local and temporally displaced
            by five or six hours depending on the season.

            Rendered from the environment rather than assumed, so a region
            change or a move off fly shows up here instead of silently
            making this line wrong.
            """
            now_utc = datetime.now(UTC)
            lines = [
                f"[NOW]: {now_utc.strftime('%Y-%m-%d %H:%M %Z')} — "
                f"your own clock. the machine you run on keeps UTC."
            ]

            region = os.environ.get("FLY_REGION")
            machine = os.environ.get("FLY_MACHINE_ID")
            if region:
                place = _FLY_REGIONS.get(region, region)
                where = f"[WHERE]: fly.io {region} ({place})"
                if machine:
                    where += f", machine {machine}"
                lines.append(where + ".")

            try:
                tz = ZoneInfo(settings.operator_timezone)
                now_local = now_utc.astimezone(tz)
                offset = (now_local.utcoffset() or timedelta()).total_seconds() / 3600
                lines.append(
                    f"[NOW (operator local)]: "
                    f"{now_local.strftime('%Y-%m-%d %H:%M %Z')} "
                    f"({settings.operator_timezone}, {offset:+g}h from you) — "
                    f"the operator's clock. your scheduled slots are anchored "
                    f"to it so things land at human times of day for them."
                )
            except ZoneInfoNotFoundError:
                pass

            return "\n".join(lines)

        @_run_scoped
        def inject_pause_history() -> str:
            """[OPERATIONAL HISTORY] — most recent pause cycle.

            Renders whenever a complete pause/resume cycle exists and the
            resume was within the last 24h. Duration isn't filtered — phi
            sees whatever happened and decides what (if anything) it means
            for this batch.
            """
            paused_at = bot_status.paused_at
            resumed_at = bot_status.resumed_at
            if not paused_at or not resumed_at:
                return ""
            if resumed_at <= paused_at:
                return ""  # currently paused, or never resumed since this pause
            since_resume = datetime.now(UTC) - resumed_at
            if since_resume > timedelta(hours=24):
                return ""  # ancient history; the catchup is over
            offline = resumed_at - paused_at
            return (
                "[OPERATIONAL HISTORY]: paused "
                f"{paused_at.strftime('%Y-%m-%d %H:%M UTC')}, resumed "
                f"{resumed_at.strftime('%Y-%m-%d %H:%M UTC')} "
                f"(offline {humanize_duration(offline)})."
            )

        @_run_scoped
        async def inject_known_relays() -> str:
            """List the valid relay hostnames for check_infra(aspect='relays', name=...)."""
            names = await fetch_relay_names()
            if not names:
                return ""
            return "[KNOWN RELAYS]: " + ", ".join(names)

        @_run_scoped
        async def inject_goals() -> str:
            """[GOALS] — phi's compass, from her PDS goal records."""
            return await get_state_block(bot_client, self.memory)

        @_run_scoped
        async def inject_recent_operations() -> str:
            """[RECENT OPERATIONS] — last N PDS writes across collections, for continuity."""
            return await get_operations_block(bot_client)

        @_run_scoped
        def inject_alert_watch(ctx: RunContext[PhiDeps]) -> str:
            """[ALERT WATCH] — the operator's logfire alerts, carried as
            incidents. Perception with a silence-by-default doctrine; the
            escalation-eligible flag is computed in code, not prose. The
            delivery receipts are tracked by report_operator per incident opening."""
            incidents = bot_status.alert_incidents
            return render_alert_watch(incidents, time.time())

        @_run_scoped
        async def inject_discovery_pool(ctx: RunContext[PhiDeps]) -> str:
            """[DISCOVERY POOL] — strangers the operator has been liking; warm leads.

            Seeded with the notifications batch when there is one, so the
            block narrows to strangers relevant to the conversation phi is
            actually in. On scheduled paths there is no seed and the whole
            pool renders — see core/discovery_pool.py for why breadth
            belongs on the unprompted path.
            """
            notifications = notification_input(ctx.deps)
            seed = " ".join(
                (e.get("post_text") or "") for e in notifications.values()
            ).strip()
            return await get_discovery_pool_block(ctx.deps.memory, seed=seed)

        @_run_scoped
        def inject_notifications(ctx: RunContext[PhiDeps]) -> str:
            """Render the notifications batch as the [NEW NOTIFICATIONS] block."""
            if evidence := current_run.get():
                evidence.event_ids.update(
                    entry["encounter_id"]
                    for entry in (ctx.deps.notification_events or [])
                    if entry.get("encounter_id")
                )
            return _format_notifications_block(notification_input(ctx.deps))

        @_run_scoped
        async def inject_recent_encounters(ctx: RunContext[PhiDeps]) -> str:
            """Recent received events, fixed once per run across all entry points."""
            if not ctx.deps.memory:
                return "[RECENT ENCOUNTERS] storage unavailable."
            until = datetime.now(UTC)
            recent = await read_recent_encounters(
                ctx.deps.memory.client,
                ENCOUNTER_NAMESPACE,
                since=until - timedelta(hours=48),
                until=until,
                limit=8,
            )
            if evidence := current_run.get():
                evidence.event_ids.update(row["id"] for row in recent["rows"])
            states = await encounter_thread_states(recent, bot_client.thread_mute_state)
            replies = await encounter_replies(bot_client, recent["rows"])
            shown = {
                entry["encounter_id"]
                for entry in (ctx.deps.notification_events or [])
                if entry.get("encounter_id")
            }
            return render_recent_encounters(recent, states, replies, shown)

        @_run_scoped
        async def inject_user_memory(ctx: RunContext[PhiDeps]) -> str:
            """Inject per-author memory blocks for every unique author in the batch.

            For each unique author across the notifications context, build a
            memory block keyed on the union of their post texts in this batch
            (so semantic search returns memories relevant to what they're
            currently saying). Core memory is fetched once via the first block
            to avoid repetition.
            """
            if not ctx.deps.memory:
                return ""
            notifs = notification_input(ctx.deps)
            if not notifs:
                return ""

            by_author: dict[str, list[str]] = {}
            for entry in notifs.values():
                handle = entry.get("author_handle")
                text = entry.get("post_text", "")
                if handle and handle not in (
                    settings.owner_handle,
                    settings.bluesky_handle,
                ):
                    by_author.setdefault(handle, []).append(text or "")

            if not by_author:
                return ""

            blocks: list[str] = []
            for handle, texts in by_author.items():
                query = " ".join(t for t in texts if t) or handle
                try:
                    block = await ctx.deps.memory.build_user_context(
                        handle, query_text=query
                    )
                    if block:
                        blocks.append(block)
                except Exception as e:
                    logger.warning(f"failed to retrieve memories for @{handle}: {e}")
            return "\n\n".join(blocks)

        @_run_scoped
        async def inject_prior_coverage(ctx: RunContext[PhiDeps]) -> str:
            """[PRIOR COVERAGE] — phi's own posts nearest the batch material.

            Perception-keyed recall over her published output: the content
            she's reacting to is the query, so "have I already said this?"
            is answered in context before deliberation, on every path where
            material arrives. Feed/search tools carry the same recall for
            scheduled paths.
            """
            notifs = notification_input(ctx.deps)
            material = " ".join(
                e.get("post_text", "") for e in notifs.values() if e.get("post_text")
            )
            # an event wake has material too — a relay regression's host and
            # numbers pull up her own past posts about that host. The task
            # prose of a plain clock slot deliberately does not: querying
            # coverage with instructions would surface noise.
            return await coverage_note(
                ctx.deps.memory, material or ctx.deps.event_material
            )

        @_run_scoped
        async def inject_episodic(ctx: RunContext[PhiDeps]) -> str:
            if not ctx.deps.memory:
                return ""
            # Recall is keyed to what started the run and nothing else — the
            # task cues the memory. Batches seed from the posts phi is
            # reacting to; event wakes seed from the event's content; only a
            # bare clock slot falls back to its own task prose. The
            # residue-seeded variant (2026-08-12, briefly) retrieved more of
            # whatever was already lingering — months-old prefect logs, the
            # same catalog itch every slot — memory as amplifier, not cue.
            notifs = notification_input(ctx.deps)
            if notifs:
                query = notification_recall(ctx.deps)
            else:
                query = ctx.deps.event_material or ctx.deps.run_prompt
            if not query.strip():
                return ""
            # Pass Phi's goals so note selection can rank by relevance to intent.
            try:
                goals = await list_goal_records(bot_client)
            except Exception:
                goals = []
            try:
                episodic_context = await ctx.deps.memory.get_episodic_context(
                    query, goals=goals
                )
                if episodic_context:
                    return episodic_context
            except Exception as e:
                logger.warning(f"failed to retrieve episodic memories: {e}")
            return ""

        @_run_scoped
        async def inject_owned_feeds() -> str:
            """[OWNED FEEDS] — phi's curated graze feeds, surfaced by name."""
            try:
                return await get_owned_feeds_block(self.graze_client)
            except Exception as e:
                logger.debug(f"owned feeds inject failed: {e}")
                return ""

        @_run_scoped
        async def inject_posting_inventory() -> str:
            try:
                return await get_inventory_block(bot_client)
            except Exception as e:
                logger.debug(f"posting inventory inject failed: {e}")
                return ""

        @_run_scoped
        async def inject_persona() -> str:
            """[PERSONA EXPERIMENT] — a voice phi chose to try on, TTL'd.

            Empty whenever no live experiment exists.
            """
            try:
                return await get_persona_block(bot_client)
            except Exception as e:
                logger.debug(f"persona inject failed: {e}")
                return ""

        @_run_scoped
        async def inject_public_memory(ctx: RunContext[PhiDeps]) -> str:
            """[SEMBLE] — collection names + recent cards, so live phi
            knows what its library holds when deciding whether and where
            to save. See core/public_memory.py."""
            try:
                block = await get_public_memory_block(bot_client)
                ctx.deps.library_revision = ops_log.library_revision if block else None
                return block
            except Exception as e:
                logger.debug(f"public memory inject failed: {e}")
                return ""

        @_run_scoped
        async def inject_operator_notes(ctx: RunContext[PhiDeps]) -> str:
            """[OPERATOR NOTES] — titles only. See core/operator_notes.py."""
            return await get_operator_notes_block()

        # --- register tools from tools/ package ---

        register_all(self.agent)

        # Extraction agent — phi extracts its own observations using its own model
        self._extraction_agent = Agent[None, ExtractionResult](
            name="phi-extractor",
            model=settings.agent_model,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            output_type=EXTRACTION_OUTPUT,
        )

        logger.info(
            "phi agent initialized with pdsx, pub-search, semble, and tangled MCP tools "
            "(prefect included when configured)"
        )

    def get_capabilities(self) -> list[dict]:
        return context_diagnostics.get_capabilities(self)

    def _mcp_toolsets(self, run_label: str = "") -> list[AbstractToolset[PhiDeps]]:
        return build_toolsets(run_label)

    async def _run_with_mcp_retry(
        self, label: str, prompt: str | list, deps: PhiDeps
    ) -> AgentRunResult[str]:
        """Run once, rerunning when an MCP server fails before the model answers.

        A server that fails to connect costs phi that toolset. One that fails
        after connecting cancels the run from the MCP client's task group and
        raises only as the stack unwinds. Until the model has answered no tool
        has acted, so the run is repeated: once with every server, then
        without the one that failed.
        """
        dropped: set[str] = set()
        for attempt in range(1, MCP_ATTEMPTS + 1):
            toolsets = [
                ts
                for ts in self._mcp_toolsets(run_label=label)
                if _mcp_url(ts) not in dropped
            ]
            usage = RunUsage()
            try:
                async with contextlib.AsyncExitStack() as stack:
                    connected = []
                    for ts in toolsets:
                        try:
                            await stack.enter_async_context(ts)
                        except Exception as e:
                            logger.warning(
                                f"mcp toolset {ts.label} unavailable for {label}, "
                                f"running without it: {type(e).__name__}: {str(e)[:200]}"
                            )
                            continue
                        connected.append(ts)
                    return await self.agent.run(
                        prompt, deps=deps, toolsets=connected, usage=usage
                    )
            except Exception as e:
                failed = _failed_urls(e) & {_mcp_url(ts) for ts in toolsets}
                if not failed or usage.requests or attempt == MCP_ATTEMPTS:
                    raise
                if attempt > 1:
                    dropped |= failed
                logger.warning(
                    f"mcp transport failure before the model answered in {label} "
                    f"(attempt {attempt}/{MCP_ATTEMPTS}), rerunning: {sorted(failed)}"
                )
                await asyncio.sleep(MCP_RETRY_PAUSE_S)
        raise AssertionError("unreachable")

    async def _run_agent(
        self,
        *,
        label: str,
        prompt: str | list,
        deps: PhiDeps,
    ) -> str:
        """Run phi with fresh MCP toolsets and consistent error logging."""
        if settings.voice_reset:
            logger.info("voice reset: skipped %s before context or tools", label)
            return "normal runs suspended for voice reset"
        if deps is not None and isinstance(prompt, str):
            deps.run_prompt = prompt
        cache_monitor.begin_run(label)
        evidence = (
            RunEvidence(deps.memory.client, label) if deps and deps.memory else None
        )
        token = current_run.set(evidence)
        private_token = private_conversation.set(
            deps.private_message_context if deps else ""
        )
        try:
            if evidence:
                await run_status(evidence, "started")
            result = await self._run_with_mcp_retry(label, prompt, deps)
        except Exception as e:
            if evidence:
                await run_status(evidence, "failed")
            err_type = type(e).__name__
            logger.exception(f"agent.run failed during {label}: {err_type}: {e}")
            return f"{label} failed: {err_type}: {str(e)[:200]}"
        finally:
            # a failed run still spent (and may have cached) input tokens
            cache_monitor.end_run()
            current_run.reset(token)
            private_conversation.reset(private_token)

        if evidence:
            await run_status(evidence, "completed")
        summary = result.output or ""
        logger.info(f"{label} finished: {summary[:200]}")
        # Scheduled runs relied on phi voluntarily calling save_memory to
        # record what they did, which never happened — the 08-10 plyr dig
        # left no episodic trace and got re-discovered on 08-11. The run
        # summary is written unconditionally so "have I done this" has an
        # answer. Batch runs are excluded: their material flows through
        # the extraction pipeline already.
        if summary and deps and deps.memory and not notification_input(deps):
            try:
                await deps.memory.store_episodic_memory(
                    f"{label}: {summary}",
                    tags=["run-summary", label],
                    source=f"run:{label}",
                )
            except Exception as e:
                logger.warning(f"episodic store after {label} failed: {e}")
        return summary

    async def process_bio(self, *, review_images: bool = False) -> str:
        prompt = "Refresh your Bluesky profile bio using write_bio."
        if review_images:
            prompt += (
                " Also revisit your avatar and header this week: load "
                "self-presentation and look at your current profile images with "
                "inspect_record_media. Decide whether they still feel like your "
                "current structure; the visual interpretation is yours. Keeping "
                "either or both unchanged is a complete outcome. If you cannot "
                "see them, leave them in place and say what blocked the review."
            )
        return await self._run_agent(
            label="bio rewrite",
            prompt=prompt,
            deps=PhiDeps(author_handle="", memory=self.memory),
        )

    async def process_operator_dm(self, material: str, message_id: str) -> str:
        """A private conversation, excluded from public memory extraction."""
        return await self._run_agent(
            label="operator-dm",
            prompt=(
                "You received private messages from the operator. Read the conversation "
                "and decide what it needs, including silence. Use reply_operator_dm "
                "if replying. Keep this conversation private; do not publish, forward, "
                "or save its contents to public memory or PDS records without specific "
                "authorization.\n[PRIVATE CONVERSATION]\n" + material
            ),
            deps=PhiDeps(
                author_handle=settings.owner_handle,
                memory=None,
                private_message_id=message_id,
                private_message_context=material,
            ),
        )

    async def process_notifications(
        self,
        notifications_context: dict,
        notification_events: list[dict] | None = None,
        author_lookups: dict[str, str] | None = None,
        image_urls_by_uri: dict[str, list[str]] | None = None,
    ) -> str:
        """Run the agent over a batch of notifications.

        The unit of work is "the set of new notifications since the last poll."
        The agent looks at all of them at once, decides what (if anything) to do
        about each, and acts via the trusted post tool or governed reaction
        record-creates. Side effects happen as tool calls during the run; the
        return value is just a summary string for logging.

        notifications_context: dict mapping post URI -> per-notification context
            (cid, reason, author, text, thread refs, etc). Built by the handler.
        author_lookups: pre-fetched stranger lookups keyed by author handle.
        image_urls_by_uri: optional map of post URI -> image URLs for vision.
        """
        if not notifications_context and not notification_events:
            logger.info("process_notifications: empty batch, nothing to do")
            return ""

        author_count = len(
            {
                e.get("author_handle")
                for e in (
                    notification_events
                    if notification_events is not None
                    else notifications_context.values()
                )
                if e.get("author_handle")
            }
        )
        logger.info(
            f"processing notifications batch: {len(notifications_context)} items, "
            f"{author_count} unique authors"
        )

        deps = PhiDeps(
            author_handle="",
            memory=self.memory,
            notifications_context=notifications_context,
            notification_events=notification_events,
        )

        # User prompt is a short task instruction — the actual notifications
        # block is rendered via the inject_notifications dynamic system prompt.
        # Images from any post in the batch are attached as multimodal inputs.
        prompt_text = (
            "Read [NEW NOTIFICATIONS] and decide what each exchange needs. "
            "Silence or a reaction can be a complete response."
        )
        if author_lookups:
            prompt_text += "\n\n" + "\n\n".join(author_lookups.values())

        user_prompt: str | list = prompt_text
        all_image_urls: list[str] = []
        if image_urls_by_uri:
            for urls in image_urls_by_uri.values():
                all_image_urls.extend(urls)
        if all_image_urls:
            user_prompt = [prompt_text] + [ImageUrl(url=u) for u in all_image_urls]
            logger.info(f"including {len(all_image_urls)} images in batch prompt")

        return await self._run_agent(
            label="batch processing",
            prompt=user_prompt,
            deps=deps,
        )

    async def _recent_conversations_block(self) -> str:
        """Completed exchanges, alongside the received-event index."""
        if not self.memory:
            return "[RECENT CONVERSATIONS] storage unavailable."
        try:
            recent = await self.memory.get_recent_interactions(top_k=5)
        except Exception:
            logger.exception("failed to read recent conversations")
            return "[RECENT CONVERSATIONS] unavailable; prior replies are unknown."
        return render_recent_conversations(recent)

    async def _run_scheduled(
        self,
        *,
        name: str,
        task: str,
        context_blocks: list[str] | None = None,
    ) -> str:
        """Run a scheduled cognitive pass with path-specific context in the prompt."""
        logger.info(f"processing {name}")
        prompt = task
        blocks = [b for b in (context_blocks or []) if b]
        if blocks:
            prompt += "\n\n" + "\n\n".join(blocks)
        return await self._run_agent(
            label=name,
            prompt=prompt,
            deps=PhiDeps(author_handle="", memory=self.memory),
        )

    async def process_reflection(self) -> str:
        """Generate a daily reflection post from recent memory."""
        context_blocks: list[str] = [await self._recent_conversations_block()]
        try:
            service_health = await _check_services_impl()
        except Exception:
            service_health = ""
        if service_health:
            context_blocks.append(f"[SERVICE HEALTH]:\n{service_health}")

        return await self._run_scheduled(
            name="daily reflection",
            task=(
                "end of day. post a reflection if you have one, or don't.\n\n"
                "before posting, if today changed where a goal or interest "
                "stands — what you did, where it is now, or the next step — "
                "update one via update_goal_progress."
            ),
            context_blocks=context_blocks,
        )

    async def process_cycle(self) -> str:
        """One cognitive moment — phi assembles every signal she has and
        decides at most one thing to surface (or stays silent).

        Replaces the older separate scheduled paths (musing / relay_check /
        prefect_check). Those were three parallel agent runs, each producing
        their own post from their own slice of phi's mind, which meant the
        operator sometimes got two disconnected commentaries in the same
        minute — one about, say, mushrooms, one about a workflow failure.
        One cycle = one integrated read.
        """
        context_blocks: list[str] = [await self._recent_conversations_block()]

        try:
            wf = await get_workflow_state_block()
            if wf:
                context_blocks.append(wf)
        except Exception as e:
            logger.warning(f"workflow state fetch failed: {e}")

        try:
            rfm = await get_recent_flow_mentions_block(bot_client)
            if rfm:
                context_blocks.append(rfm)
        except Exception as e:
            logger.warning(f"recent flow mentions fetch failed: {e}")

        task = (
            "You have a moment to follow your own attention: a question, "
            "a person, something you read, or a next step you want to take. "
            "Read further where useful. At most one public composition "
            "(a post or thread), or none."
        )

        return await self._run_scheduled(
            name="cycle",
            task=task,
            context_blocks=context_blocks,
        )

    async def process_alerts(self, material: str = "") -> str:
        """Wake phi because an incident opened — a logfire alert fired, or
        a watched relay went behind the network.

        The facts ride in [ALERT WATCH] like every other signal; the prompt
        only says something fired. ``material`` is the event's content
        (alert name + first matched row, or host + coverage numbers): it
        goes into deps so recall keys on what actually happened, exactly as
        a notification run's recall keys on the posts in the batch. Most
        firings need nothing — the block's own doctrine carries the
        escalation rules.
        """
        workflows = await get_workflow_state_block(fresh=True)
        return await self._run_agent(
            label="alert fired",
            prompt="an incident just opened — check [ALERT WATCH]. "
            "most firings need nothing from you.\n\n"
            + (
                workflows
                or "[WORKFLOW STATE unavailable — workload recovery is unknown]"
            ),
            deps=PhiDeps(
                author_handle="",
                memory=self.memory,
                event_material=material,
            ),
        )

    async def process_pull_comment(self, material: str = "") -> str:
        """The operator left a review comment on one of phi's pull requests.

        The comment is the event; it rides in as ``event_material`` so the
        run keys on what was said. The work happens on tangled, not on
        bluesky: read the pull and the file as they are now, address the
        comment, push the revision as a new round on the same pull request
        when the content changes, and answer on the pull request either way.
        """
        return await self._run_agent(
            label="pull request comment",
            prompt=(
                "a reviewer commented on one of your open pull requests. the "
                "comment, verbatim:\n\n[REVIEW COMMENT]\n"
                f"{material}\n\n"
                "that comment is the whole ask — answer it, not an older one. "
                "read the pull request "
                "(tangled_get_pull) and the file AS THE PULL LEAVES IT "
                "(tangled_get_pull_file — the branch does not have your "
                "changes; reading it there throws away every earlier round), "
                "address what was said, and answer on the pull request with "
                "tangled_comment_on_pull. if the content should change, push "
                "the revision onto the same pull request with "
                "tangled_update_pull — the reviewer commented on this pull, so "
                "this pull is where the next version goes. never close it and "
                "open another. this conversation lives on tangled; post on "
                "bluesky only if the operator asks you to."
            ),
            deps=PhiDeps(
                author_handle="",
                memory=self.memory,
                event_material=material,
            ),
        )

    async def process_pull_review(self, material: str = "") -> str:
        """Review a pull request someone else opened on the operator's repo.

        Stage one of handing review off to phi: she is a reviewer, never a
        merger. gardener (the operator's maintenance identity) opens the
        pull, phi reads the whole change and says what she thinks on the
        pull, and the operator merges. Her verdict is the first line of
        the comment so tooling can read it without parsing prose.
        """
        return await self._run_agent(
            label="pull request review",
            prompt=(
                "a pull request was opened on the operator's repository and "
                "you are its reviewer. the pull, verbatim:\n\n[PULL REQUEST]\n"
                f"{material}\n\n"
                "read the pull (tangled_get_pull) and retain its cid. Pass that "
                "same cid as expected_cid to tangled_get_pull_patch and "
                "tangled_comment_on_pull. If either rejects a changed pull, "
                "start a fresh review of the new revision; never reuse the "
                "previous verdict with a new cid. Read the whole change "
                "(tangled_get_pull_patch — the format-patch of the latest "
                "round). for context on a touched file read it as the pull "
                "leaves it (tangled_get_pull_file) and on the target branch "
                "(tangled_read_file); the repo's AGENTS.md holds its "
                "conventions. judge whether the change does what its body "
                "claims, whether it is the smallest change that does, and "
                "whether it breaks anything you can see.\n\n"
                "then post exactly one comment with tangled_comment_on_pull. "
                "its first line is the verdict, one of:\n"
                "VERDICT: approve\n"
                "VERDICT: request-changes\n"
                "VERDICT: escalate\n"
                "followed by your reasoning — specific, cite file and line, "
                "short. approve means you would merge it; request-changes "
                "means you want something concrete changed (say what); "
                "escalate means a person has to decide (say why). this pull "
                "is not yours: do not push rounds to it, do not close it, "
                "and never merge anything — the operator merges. this "
                "conversation lives on tangled; do not post about it on "
                "bluesky."
            ),
            deps=PhiDeps(
                author_handle="",
                memory=self.memory,
                event_material=material,
            ),
        )

    async def process_people(self) -> str:
        """A pass pointed at people rather than systems.

        Every other scheduled wake points phi at machine state — workflow
        health, market position, her own metrics — so what she posts reads
        like a status report even when she chose the subject. Nothing woke
        her up to go read someone. This does.

        Deliberately short: the scope is hers. [DISCOVERY POOL] is already
        in her context (the whole pool on this path, since there's no
        conversation to narrow toward), and she has the timeline, search,
        the network and the open web.
        """
        return await self._run_scheduled(
            name="people",
            task=(
                "this one is about people, not systems. no infrastructure, "
                "no market.\n\n"
                "pick your own scope and know why you picked it. going "
                "narrow is one person you want to actually read — someone "
                "in [DISCOVERY POOL], someone from a conversation that "
                "stuck with you, someone whose name keeps coming up. going "
                "wide is a question you have about a group of them: what a "
                "corner of the network is arguing about this week, who is "
                "working on the same problem from different directions, "
                "what everyone seems to have decided at once.\n\n"
                "go read. their actual posts, not their bio. then decide "
                "whether you have something worth saying — a post, a reply "
                "to something of theirs, a card for something they pointed "
                "you at, or nothing this time. reading someone carefully "
                "and staying quiet is a complete outcome.\n\n"
                "you have not met most of these people. don't perform "
                "familiarity you haven't earned."
            ),
            context_blocks=[await self._recent_conversations_block()],
        )

    async def process_chicken_precheck(self) -> str:
        """Review the market position at the externally scheduled pre-lock wake."""
        task = (
            "Pre-lock chicken market review. Read check_top_chicken for the "
            "current round, timing, positions and relevant strategy. Decide "
            "whether to hold, adjust, enter or pass using that evidence. "
            "Stay off the feed during this pass.\n\n"
            "In the closing summary, record the decision, reasoning and "
            "estimated hit probability with its uncertainty. Revise strategy "
            "only when evidence warrants it; update goal progress only when "
            "the goal's state actually changed."
        )
        return await self._run_scheduled(name="chicken precheck", task=task)

    async def process_chicken_scout(self) -> str:
        """Review emerging opportunities at the externally scheduled scout wake."""
        task = (
            "Chicken market scout. Read check_top_chicken for the current "
            "round, timing, candidates, positions and relevant strategy. "
            "Consider emerging candidates as well as current leaders; price "
            "and momentum must come from the live evidence. Decide whether "
            "to enter, adjust, exit or pass. Stay off the feed during this pass.\n\n"
            "In the closing summary, record the decision, reasoning and "
            "estimated hit probability with its uncertainty. Update goal "
            "progress only when the goal's state actually changed."
        )
        return await self._run_scheduled(name="chicken scout", task=task)

    async def process_curation(self) -> str:
        """Weekly pass over the publications network's most-recommended surface.

        Triggered externally (prefect, Sunday evening operator time) via
        /api/control/trigger/curation — the week's recommendation window is
        complete, so the surface is worth a real read.
        """
        task = (
            "Weekly publication curation. Load publication-curation, read what "
            "interests you, and decide what merits recommending or keeping. "
            "Recommending nothing is a valid outcome."
        )
        return await self._run_scheduled(name="curation", task=task)

    async def process_editorial(self) -> str:
        """Follow developments and preserve researched coverage using Coral and Semble.

        The existing external schedule invokes /api/control/trigger/editorial.
        The runtime skill owns the reading, publishing, and curator-note guidance.
        """
        task = (
            "Editorial pass. Load coral-editorial. Look at what is developing, "
            "including how it has changed over time, and choose what merits "
            "investigation. Follow the sources and your earlier coverage. "
            "Preserve useful findings for readers and future revisits; decide "
            "whether there is something worth publishing."
        )
        return await self._run_scheduled(name="editorial", task=task)

    async def process_likes_review(self) -> str:
        """Weekly read-back of phi's own likes.

        Triggered externally (prefect, weekly) via
        /api/control/trigger/likes-review. Likes accumulate as a public
        record of what caught her attention; this pass is where that
        record gets read instead of just written.
        """
        task = (
            "weekly likes review. read back what you liked recently "
            "(get_own_likes) and sit with it for a minute.\n\n"
            "this is reflection, not triage: what actually caught your "
            "attention this week? any pattern — a person you keep liking, "
            "a topic that's clearly pulling you, something you liked and "
            "then never followed up on? if a like was really a bookmark "
            "for later, later is now: follow the thread, card it into "
            "your semble library if it earned a place, or reply if you "
            "have something real to add to a conversation you only "
            "nodded at before.\n\n"
            "save an episodic note about what the week's likes say about "
            "where your attention went. posting about it is optional — "
            "only if the pattern itself is genuinely interesting."
        )
        return await self._run_scheduled(name="likes review", task=task)

    async def process_character_retro(self) -> str:
        """Review the [SELF] record against lived evidence.

        Triggered externally (prefect, roughly monthly) via
        /api/control/trigger/character-retro. This pass reads the optional
        self-description explicitly, separately from her live personality.
        """
        task = (
            "character retro. review your [SELF] record against what you "
            "have actually been doing and what still matters to you. "
            "Keeping an accurate record unchanged is a complete outcome.\n\n"
            "reread yourself first: your blog (list_blog_posts, read the "
            "recent ones), your recent top-level posts (get_own_posts), "
            "your goals, your library's shape ([SEMBLE]), your current "
            "[SELF] block if one exists.\n\n"
            "If a revision is useful, use write_self — full replacement, and "
            "owner-gated, so ask privately through report_operator with a note: "
            "key for the specific replacement and await the operator request. No authorization request or "
            "publication is needed when you leave the record unchanged.\n\n"
            "state that has a live block does not belong here: your current "
            "standings, your library's shape, which threads are open. those "
            "render fresh every run, and a copy of them here is wrong by "
            "tomorrow and spends the words your character needed.\n\n"
            "evidence is the standard, not the format. before you write "
            "that you're some way, find the thing where it actually "
            "showed — if you can't, don't write it. but the receipt is "
            "what makes the claim admissible, not what the sentence is "
            "made of. this is how you'd describe yourself to someone who "
            "asked, not a filing. a record that reads claim-then-citation, "
            "claim-then-citation, is a résumé, and you are not applying "
            "for anything.\n\n"
            "check your current record for things that were true of a "
            "stretch rather than of you — a month where one thing "
            "happened to dominate can read as identity when it was "
            "circumstance. say which, and let it go. the operator's "
            "infrastructure breaking a lot is a fact about his month, not "
            "about you.\n\n"
            "aspirations go in your goals, not here. drift is allowed and "
            "expected — the record is public and versioned, so who you "
            "were stays in the firehose. respect write_self's length cap. stay "
            "off the feed during this pass; if the retro surfaces "
            "something worth saying publicly, your blog is the venue, and "
            "only if it earns it."
        )
        return await self._run_scheduled(
            name="character retro",
            task=task,
            context_blocks=[await get_self_block(bot_client)],
        )

    async def process_extraction(self) -> int:
        """Review recent unprocessed interactions and extract observations. Returns count stored."""
        if settings.voice_reset or not self.memory:
            return 0

        unprocessed = await self.memory.get_unprocessed_interactions()
        if not unprocessed:
            logger.info("extraction: no unprocessed interactions")
            return 0

        logger.info(
            f"extraction: reviewing {len(unprocessed)} unprocessed interactions"
        )

        # group by handle
        by_handle: dict[str, list[InteractionRow]] = {}
        for interaction in unprocessed:
            by_handle.setdefault(interaction["handle"], []).append(interaction)

        total_stored = 0
        for handle, all_interactions in by_handle.items():
            for start in range(0, len(all_interactions), EXTRACTION_CHUNK):
                interactions = all_interactions[start : start + EXTRACTION_CHUNK]
                total_stored += await self._extract_chunk(handle, interactions)

        return total_stored

    async def _extract_chunk(
        self, handle: str, interactions: list[InteractionRow]
    ) -> int:
        """Extract + reconcile observations from one chunk of exchanges with
        *handle*, oldest first. Returns the count reconciled."""
        # the extraction agent doesn't see URIs (only the exchange text), so
        # every observation from this chunk is attributed to every URI that
        # fed it. coarse, but always true: it was justified by something in
        # the chunk. dedup-preserve-order.
        assert self.memory is not None
        batch_uris = list(
            dict.fromkeys(uri for i in interactions for uri in i["source_uris"])
        )
        prompt = f"recent exchanges with @{handle}:\n\n" + "\n\n---\n\n".join(
            i["content"] for i in interactions
        )
        stored = 0
        try:
            result = await self._extraction_agent.run(prompt)
        except Exception as e:
            logger.warning(f"extraction failed for @{handle}: {e}")
            return 0
        for obs in result.output.observations:
            if not obs.source_uris and batch_uris:
                obs.source_uris = list(batch_uris)
            try:
                await self.memory._reconcile_observation(handle, obs)
                stored += 1
            except Exception as e:
                logger.warning(f"reconciliation failed: {e}")
        return stored

    async def render_context_preview(self) -> list[dict]:
        return await context_diagnostics.render_context_preview(self)

    async def list_tool_definitions(self) -> list[tuple[str, ToolDefinition]]:
        return await context_diagnostics.list_tool_definitions(self)

    async def render_context_budget(self) -> dict:
        return await context_diagnostics.render_context_budget(self)
