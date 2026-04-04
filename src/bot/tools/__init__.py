"""Tool registration for phi agent."""

from bot.core.graze_client import GrazeClient
from bot.tools._helpers import PhiDeps, _check_services_impl


def register_all(agent, graze_client: GrazeClient):
    """Register all tools on the agent."""
    from bot.tools import blog, bluesky, cosmik, feeds, memory, search

    memory.register(agent)
    search.register(agent)
    cosmik.register(agent)
    feeds.register(agent, graze_client)
    bluesky.register(agent)
    blog.register(agent)


__all__ = ["PhiDeps", "_check_services_impl", "register_all"]
