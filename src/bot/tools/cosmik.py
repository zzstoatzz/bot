"""Cosmik record tools — URL cards and connections."""

from pydantic_ai import RunContext

from bot.tools._helpers import PhiDeps, _create_cosmik_record
from bot.types import CosmikConnection, CosmikUrlCard, UrlContent


def register(agent):
    @agent.tool
    async def save_url(
        ctx: RunContext[PhiDeps],
        url: str,
        title: str,
        description: str | None = None,
    ) -> str:
        """Save a URL as a cosmik card on your PDS. Use when you find something worth bookmarking publicly.
        Always provide a concise, descriptive title — this is what appears in the activity feed."""
        try:
            card = CosmikUrlCard(
                content=UrlContent(url=url, title=title, description=description)
            )
        except Exception as e:
            return f"validation failed: {e}"

        parts: list[str] = []

        # public: cosmik URL card on PDS
        try:
            uri = await _create_cosmik_record("network.cosmik.card", card.to_record())
            parts.append(f"card created: {uri}")
        except Exception as e:
            return f"failed to create card: {e}"

        # private: also store in turbopuffer for recall
        if ctx.deps.memory:
            desc = f"bookmarked {url}" + (f" — {title}" if title else "")
            await ctx.deps.memory.store_episodic_memory(
                desc, ["bookmark", "url"], source="tool"
            )
            parts.append("noted privately")

        return " + ".join(parts)

    @agent.tool
    async def create_connection(
        ctx: RunContext[PhiDeps],
        source: str,
        target: str,
        connection_type: str | None = None,
        note: str | None = None,
    ) -> str:
        """Create a network.cosmik.connection record — a semantic link between two entities.
        Source and target must be URLs or at:// URIs. Connection types: related, supports, opposes, addresses, helpful, explainer, leads_to, supplements."""
        try:
            conn = CosmikConnection(
                source=source,
                target=target,
                connection_type=connection_type,
                note=note,
            )
        except Exception as e:
            return f"validation failed: {e}"

        try:
            uri = await _create_cosmik_record(
                "network.cosmik.connection", conn.to_record()
            )
            return f"connection created: {uri}"
        except Exception as e:
            return f"failed to create connection: {e}"
