"""MCP-enabled agent for phi with structured memory."""

import logging
import os
from pathlib import Path

import httpx
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServerStreamableHTTP

from bot.config import settings
from bot.memory import NamespaceMemory

logger = logging.getLogger("bot.agent")


class Response(BaseModel):
    """Agent response indicating what action to take."""

    action: str  # "reply", "like", "ignore", "repost"
    text: str | None = None
    reason: str | None = None


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
            self.memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)
            logger.info("memory enabled (turbopuffer)")
        else:
            self.memory = None
            logger.warning("no memory - missing turbopuffer or openai key")

        # Generic atproto record CRUD via hosted pdsx MCP
        pdsx_mcp = MCPServerStreamableHTTP(
            url="https://pdsx-by-zzstoatzz.fastmcp.app/mcp",
            timeout=30,
            headers={
                "x-atproto-handle": settings.bluesky_handle,
                "x-atproto-password": settings.bluesky_password,
            },
        )

        # ATProto publication search via hosted pub-search MCP
        pub_search_mcp = MCPServerStreamableHTTP(
            url="https://pub-search-by-zzstoatzz.fastmcp.app/mcp",
            timeout=30,
            tool_prefix="pub",
        )

        # Create PydanticAI agent with MCP tools
        self.agent = Agent[dict, Response](
            name="phi",
            model="anthropic:claude-3-5-haiku-latest",
            system_prompt=self.base_personality,
            output_type=Response,
            deps_type=dict,
            toolsets=[pdsx_mcp, pub_search_mcp],
        )

        # Register search_memory tool on the agent
        @self.agent.tool
        async def search_memory(ctx: RunContext[dict], query: str) -> str:
            """Search your memory for information about the current user. Use this when you want more context about past interactions or facts you know about them."""
            handle = ctx.deps.get("author_handle")
            memory = ctx.deps.get("memory")
            if not handle or not memory:
                return "memory not available"

            results = await memory.search(handle, query, top_k=10)
            if not results:
                return "no relevant memories found"

            parts = []
            for r in results:
                kind = r.get("kind", "unknown")
                content = r.get("content", "")
                tags = r.get("tags", [])
                tag_str = f" [{', '.join(tags)}]" if tags else ""
                parts.append(f"[{kind}]{tag_str} {content}")
            return "\n".join(parts)

        @self.agent.tool
        async def get_trending(ctx: RunContext[dict]) -> str:
            """Get what's currently trending on Bluesky. Returns entity-level trends from the firehose (via coral) and official Bluesky trending topics. Use this when someone asks about current events, what people are talking about, or when you want timely context."""
            parts: list[str] = []

            async with httpx.AsyncClient(timeout=15) as client:
                # coral entity graph — NER-extracted trending entities from the firehose
                try:
                    r = await client.get("https://coral.fly.dev/entity-graph")
                    r.raise_for_status()
                    data = r.json()
                    entities = data.get("entities", [])
                    stats = data.get("stats", {})

                    by_trend = sorted(
                        entities, key=lambda e: e.get("trend", 0), reverse=True
                    )[:15]

                    lines = [
                        f"coral ({stats.get('active', 0)} active entities, "
                        f"{stats.get('clusters', 0)} clusters"
                        f"{', percolating' if stats.get('percolates') else ''}):"
                    ]
                    for e in by_trend:
                        lines.append(
                            f"  {e['text']} ({e.get('label', '')}) "
                            f"trend={e.get('trend', 0):.2f}"
                        )
                    parts.append("\n".join(lines))
                except Exception as e:
                    parts.append(f"coral unavailable: {e}")

                # official bluesky trending topics
                try:
                    r = await client.get(
                        "https://public.api.bsky.app/xrpc/app.bsky.unspecced.getTrendingTopics"
                    )
                    r.raise_for_status()
                    topics = r.json().get("topics", [])
                    if topics:
                        lines = ["bluesky trending:"]
                        for t in topics[:15]:
                            lines.append(f"  {t.get('displayName', t.get('topic', ''))}")
                        parts.append("\n".join(lines))
                except Exception as e:
                    parts.append(f"bluesky trending unavailable: {e}")

            return "\n\n".join(parts) if parts else "no trending data available"

        logger.info("phi agent initialized with pdsx + pub-search mcp tools")

    async def process_mention(
        self,
        mention_text: str,
        author_handle: str,
        thread_context: str,
        thread_uri: str | None = None,
    ) -> Response:
        """Process a mention with structured memory context."""
        # Build context from memory if available
        memory_context = ""
        if self.memory:
            try:
                memory_context = await self.memory.build_user_context(
                    author_handle, query_text=mention_text, include_core=True
                )
                logger.info(f"memory context for @{author_handle}: {len(memory_context)} chars")
            except Exception as e:
                logger.warning(f"failed to retrieve memories: {e}")

        # Build full prompt with clearly labeled context sections
        prompt_parts = []

        if thread_context and thread_context != "No previous messages in this thread.":
            prompt_parts.append(f"[CURRENT THREAD - these are the messages in THIS thread]:\n{thread_context}")

        if memory_context:
            prompt_parts.append(f"[PAST CONTEXT WITH @{author_handle}]:\n{memory_context}")

        prompt_parts.append(f"\n[NEW MESSAGE]:\n@{author_handle}: {mention_text}")
        prompt = "\n\n".join(prompt_parts)

        # Run agent with MCP tools + search_memory available
        logger.info(f"processing mention from @{author_handle}: {mention_text[:80]}")
        deps = {
            "thread_uri": thread_uri,
            "author_handle": author_handle,
            "memory": self.memory,
        }
        result = await self.agent.run(prompt, deps=deps)
        logger.info(f"agent decided: {result.output.action}" + (f" - {result.output.text[:80]}" if result.output.text else "") + (f" ({result.output.reason})" if result.output.reason else ""))

        # Store interaction and extract observations
        if self.memory and result.output.action == "reply" and result.output.text:
            try:
                await self.memory.after_interaction(
                    author_handle, mention_text, result.output.text
                )
            except Exception as e:
                logger.warning(f"failed to store interaction: {e}")

        return result.output
