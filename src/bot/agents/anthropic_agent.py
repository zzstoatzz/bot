"""Anthropic agent for generating responses"""

import logging
import os

from pydantic_ai import Agent, RunContext

from bot.agents._personality import load_personality
from bot.agents.base import Response
from bot.config import settings
from bot.memory import NamespaceMemory
from bot.personality import request_operator_approval
from bot.tools.google_search import search_google
from bot.tools.personality_tools import (
    reflect_on_interest,
    update_self_reflection,
    view_personality_section,
)

logger = logging.getLogger("bot.agent")


class AnthropicAgent:
    """Agent that uses Anthropic Claude for responses"""

    def __init__(self):
        if settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

        self.agent = Agent(
            "anthropic:claude-3-5-haiku-latest",
            system_prompt=load_personality(),
            output_type=Response,
        )

        # Register search tool if available
        if settings.google_api_key:

            @self.agent.tool
            async def search_web(ctx: RunContext[None], query: str) -> str:
                """Search the web for current information about a topic"""
                return await search_google(query)

        if settings.turbopuffer_api_key and os.getenv("OPENAI_API_KEY"):
            self.memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)

            @self.agent.tool
            async def examine_personality(ctx: RunContext[None], section: str) -> str:
                """Look at a section of my personality (interests, current_state, communication_style, core_identity, boundaries)"""
                return await view_personality_section(self.memory, section)

            @self.agent.tool
            async def add_interest(
                ctx: RunContext[None], topic: str, why_interesting: str
            ) -> str:
                """Add a new interest to my personality based on something I find engaging"""
                return await reflect_on_interest(self.memory, topic, why_interesting)

            @self.agent.tool
            async def update_state(ctx: RunContext[None], reflection: str) -> str:
                """Update my current state/self-reflection"""
                return await update_self_reflection(self.memory, reflection)

            @self.agent.tool
            async def request_identity_change(
                ctx: RunContext[None], section: str, proposed_change: str, reason: str
            ) -> str:
                """Request approval to change core_identity or boundaries sections of my personality"""
                if section not in ["core_identity", "boundaries"]:
                    return f"Section '{section}' doesn't require approval. Use other tools for interests/state."

                approval_id = request_operator_approval(
                    section, proposed_change, reason
                )
                if approval_id:
                    return f"Approval request #{approval_id} sent to operator. They will review via DM."
                else:
                    return "Failed to create approval request."
        else:
            self.memory = None

    async def generate_response(
        self, mention_text: str, author_handle: str, thread_context: str = ""
    ) -> Response:
        """Generate a response to a mention"""
        # Build the full prompt with thread context
        prompt_parts = []

        if thread_context and thread_context != "No previous messages in this thread.":
            prompt_parts.append(thread_context)
            prompt_parts.append("\nNew message:")

        prompt_parts.append(f"{author_handle} said: {mention_text}")

        prompt = "\n".join(prompt_parts)

        logger.info(f"🤖 Processing mention from @{author_handle}")
        logger.debug(f"📝 Mention text: '{mention_text}'")
        if thread_context:
            logger.debug(f"🧵 Thread context: {thread_context}")
        logger.debug(f"🤖 Full prompt:\n{prompt}")

        # Run agent and capture tool usage
        result = await self.agent.run(prompt)

        # Log the full output for debugging
        logger.debug(
            f"📊 Full output: action={result.output.action}, "
            f"reason='{result.output.reason}', text='{result.output.text}'"
        )

        return result.output
