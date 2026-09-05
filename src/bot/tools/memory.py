"""Memory tools — private search_memory (read) and save_memory (write)."""

import json
from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext

from bot.memory.encounter_search import read_encounter as read_source_encounter
from bot.memory.encounter_search import read_encounter_activity
from bot.memory.encounter_search import search_encounters as search_source_encounters
from bot.memory.encounters import ENCOUNTER_NAMESPACE
from bot.memory.search_status import IncompleteMemorySearch
from bot.tools._helpers import (
    PhiDeps,
    _format_episodic_results,
    _format_unified_results,
    _format_user_results,
)


def register(agent):
    @agent.tool
    async def search_encounters(
        ctx: RunContext[PhiDeps],
        query: Annotated[str, Field(description="words from the interaction to find")],
    ) -> str:
        """Search captured incoming notifications across people without a handle.

        Results are received source events, not evidence of your response or
        intent. Older uncaptured exchanges may exist in search_memory. Use
        read_encounter with a result ID to retrieve its full stored record.
        """
        if not ctx.deps.memory:
            return "Encounter storage is unavailable."
        result = await search_source_encounters(
            ctx.deps.memory.client, ENCOUNTER_NAMESPACE, query
        )
        if result["status"] != "ok":
            return f"Encounter search {result['status']}; this does not establish absence of an interaction."
        rows = [
            {
                **{
                    key: row.get(key)
                    for key in (
                        "id",
                        "actor_did",
                        "actor_handle",
                        "reason",
                        "event_uri",
                        "event_cid",
                        "indexed_at",
                        "captured_at",
                        "source_uris",
                    )
                },
                "excerpt": (row.get("content") or "")[:300],
            }
            for row in result["rows"]
        ]
        return json.dumps(
            {
                "coverage": "Captured incoming notifications only; text matches, not exhaustive history. Responses and decisions are not represented.",
                "results": rows,
                "has_more_matches": result["has_more"],
            },
            ensure_ascii=False,
        )

    @agent.tool
    async def read_encounter(
        ctx: RunContext[PhiDeps],
        event_id: Annotated[
            str, Field(description="encounter ID from search or recent context")
        ],
    ) -> str:
        """Read a captured notification's original record and source references.

        Its capture timestamp proves storage, not model exposure or a decision.
        """
        if not ctx.deps.memory:
            return "Encounter storage is unavailable."
        result = await read_source_encounter(
            ctx.deps.memory.client, ENCOUNTER_NAMESPACE, event_id
        )
        activity = await read_encounter_activity(
            ctx.deps.memory.client, ENCOUNTER_NAMESPACE, event_id
        )
        return json.dumps(
            {
                "source": result,
                "processing_evidence": activity,
                "meaning": "Prepared input does not prove delivery. A received response or completed run does not prove a public action or explain silence. Open the referenced execution traces for confirmed tool results and dated statements.",
            },
            ensure_ascii=False,
        )

    @agent.tool
    async def search_memory(
        ctx: RunContext[PhiDeps],
        query: Annotated[
            str, Field(description="what to look for in your private memory")
        ],
        about: Annotated[
            str,
            Field(
                description=(
                    "optional @handle to scope the search to one user's "
                    "namespace; empty searches your episodic notes plus the "
                    "current author's namespace together"
                )
            ),
        ] = "",
        tag: Annotated[
            str,
            Field(
                description=(
                    "optional tag to filter episodic results by (e.g. "
                    "'correction' to audit what you've gotten wrong)"
                )
            ),
        ] = "",
    ) -> str:
        """Search your private memory. Use to find past conversations and
        things you've explicitly saved.

        Results include stored source URIs when available; open them to
        inspect the original exchange or document.

        Without `about`: searches two places at once — your episodic notes
        (written via `save_memory`) and the current conversation author's
        namespace.

        With `about="@handle"`: searches that user's namespace only.
        Use search_people for a name clue when you don't know the handle.

        With `tag`: only episodic notes carrying that tag come back —
        `tag="correction"` is how you audit your own errata.

        For public network knowledge, use the semble tools instead.
        Write-side companion: `save_memory` (episodic notes)."""
        try:
            return await _search_private(ctx, query, about, tag)
        except IncompleteMemorySearch as error:
            partial = "\n".join(
                _format_unified_results(error.results, ctx.deps.author_handle)
            )
            return (
                f"Memory search incomplete ({error}). This is not evidence of no prior encounter."
                + (f"\nAvailable results:\n{partial}" if partial else "")
            )
        except Exception:
            return "Memory search failed; history is unavailable for this query. This is not evidence of no prior encounter."

    @agent.tool
    async def save_memory(
        ctx: RunContext[PhiDeps],
        content: Annotated[
            str, Field(description="the memory to save, as a short statement")
        ],
        tags: Annotated[
            list[str],
            Field(description="0-3 lowercase topic tags to find it by later"),
        ],
        source_uri: Annotated[
            str,
            Field(
                description=(
                    "AT-URI of the post/thread/card this memory is grounded "
                    "in, when there is one — makes it checkable later"
                )
            ),
        ] = "",
    ) -> str:
        """Save something to your private memory.

        Two ways it comes back: ambient recall (relevant notes ride into
        your context at the start of a run, keyed to what you're
        processing) and explicit `search_memory`.

        Stores your wording exactly and returns the saved note ID, text, and
        citations. Related older versions remain in memory as superseded records.

        Re-saving a refined version of something you remember SUPERSEDES
        the old row — write-time reconciliation patches it with pedigree.
        This is how you edit your memory: save the better version, the
        stale one retires.

        Tag `correction` when recording that you got something wrong
        (claim, fix, and the post uri where you corrected it). Correction
        notes never fade from recall the way ordinary notes do. The
        corrected FACT belongs in your semble library only if it earns a
        place on its own — filed under its subject, never under the
        mistake.

        Pass source_uri when the memory is grounded in a specific post,
        thread, or card you can cite — it makes it checkable later.
        """
        if ctx.deps.memory:
            sources = [source_uri] if source_uri else None
            saved = await ctx.deps.memory.store_episodic_memory(
                content, tags, source="tool", source_uris=sources, preserve_text=True
            )
            return json.dumps(
                {
                    "stored_note": saved,
                    "meaning": "The resulting saved account after reconciliation; its claims and citations are not independently verified.",
                },
                ensure_ascii=False,
            )
        return "private memory not available"


async def _search_private(ctx, query: str, about: str, tag: str) -> str:
    if not ctx.deps.memory:
        return "memory not available"

    if tag:
        results = await ctx.deps.memory.search_episodic(query, top_k=30)
        results = [r for r in results if tag in (r.get("tags") or [])][:10]
        if not results:
            return f"no memories tagged '{tag}' match that query"
        return "\n".join(_format_episodic_results(results))

    if about.startswith("@"):
        handle = about.lstrip("@")
        results = await ctx.deps.memory.search(handle, query, top_k=10)
        if not results:
            return f"no memories found about @{handle}"
        return "\n".join(_format_user_results(results, handle))

    if about == "":
        results = await ctx.deps.memory.search_unified(
            ctx.deps.author_handle, query, top_k=8
        )
        if not results:
            return "no relevant memories found"
        return "\n".join(_format_unified_results(results, ctx.deps.author_handle))

    # bare handle without @
    results = await ctx.deps.memory.search(about, query, top_k=10)
    if not results:
        return f"no memories found about @{about}"
    return "\n".join(_format_user_results(results, about))
