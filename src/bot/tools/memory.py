"""Memory tools — private recall and note-taking."""

from pydantic_ai import RunContext

from bot.tools._helpers import (
    PhiDeps,
    _format_unified_results,
    _format_user_results,
)


def register(agent):
    @agent.tool
    async def recall(ctx: RunContext[PhiDeps], query: str, about: str = "") -> str:
        """Search your private memory. Use to remember past conversations and what you know about specific people.
        Pass about="@handle" to search a specific user, or leave empty for general private recall.
        For public network knowledge, use search_network instead."""
        if not ctx.deps.memory:
            return "memory not available"

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

    @agent.tool
    async def note(ctx: RunContext[PhiDeps], content: str, tags: list[str]) -> str:
        """Leave a note for your future self. Stored privately for fast vector recall."""
        if ctx.deps.memory:
            await ctx.deps.memory.store_episodic_memory(content, tags, source="tool")
            return f"noted — {content[:100]}"
        return "private memory not available"
