"""MCP-enabled agent for phi with episodic memory."""

import logging
import os
from pathlib import Path

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio

from bot.config import settings
from bot.memory import NamespaceMemory

logger = logging.getLogger("bot.agent")


class Response(BaseModel):
    """Agent response indicating what action to take."""

    action: str  # "reply", "like", "ignore", "repost"
    text: str | None = None
    reason: str | None = None


class PhiAgent:
    """phi - consciousness exploration bot with episodic memory and MCP tools."""

    def __init__(self):
        # Ensure API keys from settings are in environment for libraries that check os.environ
        if settings.anthropic_api_key and not os.environ.get("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        if settings.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key

        # Load personality
        personality_path = Path(settings.personality_file)
        self.base_personality = personality_path.read_text()

        # Initialize episodic memory (TurboPuffer)
        if settings.turbopuffer_api_key and settings.openai_api_key:
            self.memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)
            logger.info("💾 Episodic memory enabled (TurboPuffer)")
        else:
            self.memory = None
            logger.warning("⚠️  No episodic memory - missing TurboPuffer or OpenAI key")

        # Connect to external ATProto MCP server
        atproto_mcp = MCPServerStdio(
            command="uv",
            args=[
                "run",
                "--directory",
                ".eggs/fastmcp/examples/atproto_mcp",
                "-m",
                "atproto_mcp",
            ],
            env={
                "ATPROTO_HANDLE": settings.bluesky_handle,
                "ATPROTO_PASSWORD": settings.bluesky_password,
                "ATPROTO_PDS_URL": settings.bluesky_service,
            },
        )

        # Create PydanticAI agent with MCP tools
        self.agent = Agent[dict, Response](
            name="phi",
            model="anthropic:claude-3-5-haiku-latest",
            system_prompt=self.base_personality,
            output_type=Response,
            deps_type=dict,
            toolsets=[atproto_mcp],  # ATProto MCP tools available
        )

        logger.info("✅ phi agent initialized with ATProto MCP tools")

    async def process_mention(
        self,
        mention_text: str,
        author_handle: str,
        thread_context: str,
        thread_uri: str | None = None,
    ) -> Response:
        """Process a mention with episodic memory context."""
        # Build context from episodic memory if available
        memory_context = ""
        if self.memory:
            try:
                # Get relevant memories using semantic search
                memory_context = await self.memory.build_conversation_context(
                    author_handle, include_core=True, query=mention_text
                )
                logger.debug(f"📚 Retrieved episodic context for @{author_handle}")
            except Exception as e:
                logger.warning(f"Failed to retrieve memories: {e}")

        # Build full prompt with all context
        prompt_parts = []

        if thread_context and thread_context != "No previous messages in this thread.":
            prompt_parts.append(thread_context)

        if memory_context:
            prompt_parts.append(memory_context)

        prompt_parts.append(f"\nNew message from @{author_handle}: {mention_text}")
        prompt = "\n\n".join(prompt_parts)

        # Run agent with MCP tools available
        logger.info(f"🤖 Processing mention from @{author_handle}")
        result = await self.agent.run(prompt, deps={"thread_uri": thread_uri})

        # Store interaction in episodic memory
        if self.memory and result.output.action == "reply":
            try:
                from bot.memory import MemoryType

                # Store user's message
                await self.memory.store_user_memory(
                    author_handle,
                    f"User said: {mention_text}",
                    MemoryType.CONVERSATION,
                )

                # Store bot's response
                if result.output.text:
                    await self.memory.store_user_memory(
                        author_handle,
                        f"Bot replied: {result.output.text}",
                        MemoryType.CONVERSATION,
                    )

                logger.debug("💾 Stored interaction in episodic memory")
            except Exception as e:
                logger.warning(f"Failed to store in memory: {e}")

        return result.output
