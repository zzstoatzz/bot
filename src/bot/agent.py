"""MCP-enabled agent for phi using PydanticAI."""

import logging
from pathlib import Path

from pydantic import BaseModel
from pydantic_ai import Agent

from bot.atproto_mcp.server import atproto_mcp
from bot.config import settings
from bot.memory import Memory

logger = logging.getLogger("bot.agent")


class Response(BaseModel):
    """Agent response indicating what action to take."""

    action: str  # "reply", "like", "ignore"
    text: str | None = None
    reason: str | None = None


class PhiAgent:
    """phi - an MCP-enabled agent for Bluesky."""

    def __init__(self, memory: Memory | None = None):
        self.memory = memory or Memory()

        # Load personality
        personality_path = Path(settings.personality_file)
        self.personality = personality_path.read_text()

        # Create PydanticAI agent with ATProto MCP tools
        self.agent = Agent[dict, Response](
            name="phi",
            model="anthropic:claude-3-5-haiku-latest",
            system_prompt=self.personality,
            output_type=Response,
            deps_type=dict,
            toolsets=[atproto_mcp],  # ATProto MCP tools available
        )

        logger.info("✅ phi agent initialized with ATProto MCP tools")

    async def process_mention(
        self,
        mention_text: str,
        author_handle: str,
        thread_uri: str | None = None,
    ) -> Response:
        """Process a mention and decide how to respond."""
        # Build context from memory
        if thread_uri:
            context = self.memory.build_full_context(thread_uri, author_handle)
        else:
            context = self.memory.get_user_context(author_handle)

        # Build prompt
        prompt_parts = []
        if context and context != "No prior context available.":
            prompt_parts.append(context)
            prompt_parts.append("\nNew message:")

        prompt_parts.append(f"@{author_handle} said: {mention_text}")
        prompt = "\n".join(prompt_parts)

        # Run agent
        logger.info(f"🤖 Processing mention from @{author_handle}")
        result = await self.agent.run(prompt, deps={"thread_uri": thread_uri})

        # Store in memory if replying
        if thread_uri and result.output.action == "reply":
            self.memory.add_thread_message(thread_uri, author_handle, mention_text)
            if result.output.text:
                self.memory.add_thread_message(
                    thread_uri, settings.bluesky_handle, result.output.text
                )

        return result.output
