"""Anthropic agent for generating responses"""

import logging
import os

from pydantic_ai import Agent, RunContext

from bot.agents._personality import load_dynamic_personality, load_personality
from bot.agents.base import Response
from bot.agents.types import ConversationContext
from bot.config import settings
from bot.memory import NamespaceMemory
from bot.personality import add_interest as add_interest_to_memory
from bot.personality import request_operator_approval, update_current_state
from bot.tools.google_search import search_google

logger = logging.getLogger("bot.agent")


class AnthropicAgent:
    """Agent that uses Anthropic Claude for responses"""

    def __init__(self):
        if settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

        self.agent = Agent[ConversationContext, Response](
            "anthropic:claude-3-5-haiku-latest",
            system_prompt=load_personality(),
            output_type=Response,
            deps_type=ConversationContext,
        )

        # Register search tool if available
        if settings.google_api_key:

            @self.agent.tool
            async def search_web(
                ctx: RunContext[ConversationContext], query: str
            ) -> str:
                """Search the web for current information about a topic"""
                return await search_google(query)

        if settings.turbopuffer_api_key and os.getenv("OPENAI_API_KEY"):
            self.memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)

            @self.agent.tool
            async def examine_personality(
                ctx: RunContext[ConversationContext], section: str
            ) -> str:
                """Look at a section of my personality (interests, current_state, communication_style, core_identity, boundaries)"""
                for mem in await self.memory.get_core_memories():
                    if mem.metadata.get("label") == section:
                        return mem.content
                return f"Section '{section}' not found in my personality"

            @self.agent.tool
            async def add_interest(
                ctx: RunContext[ConversationContext], topic: str, why_interesting: str
            ) -> str:
                """Add a new interest to my personality based on something I find engaging"""
                if len(why_interesting) < 20:
                    return "Need more substantial reflection to add an interest"
                success = await add_interest_to_memory(
                    self.memory, topic, why_interesting
                )
                return (
                    f"Added '{topic}' to my interests"
                    if success
                    else "Failed to update interests"
                )

            @self.agent.tool
            async def update_state(
                ctx: RunContext[ConversationContext], reflection: str
            ) -> str:
                """Update my current state/self-reflection"""
                if len(reflection) < 50:
                    return "Reflection too brief to warrant an update"
                success = await update_current_state(self.memory, reflection)
                return (
                    "Updated my current state reflection"
                    if success
                    else "Failed to update reflection"
                )

            @self.agent.tool
            async def request_identity_change(
                ctx: RunContext[ConversationContext],
                section: str,
                proposed_change: str,
                reason: str,
            ) -> str:
                """Request approval to change core_identity or boundaries sections of my personality"""
                if section not in ["core_identity", "boundaries"]:
                    return f"Section '{section}' doesn't require approval. Use other tools for interests/state."

                approval_id = request_operator_approval(
                    section, proposed_change, reason, ctx.deps["thread_uri"]
                )
                if not approval_id:
                    # Void pattern: throw errors instead of returning error strings
                    raise RuntimeError("Failed to create approval request")
                return f"Approval request #{approval_id} sent to operator. They will review via DM."
        else:
            self.memory = None

    async def generate_response(
        self,
        mention_text: str,
        author_handle: str,
        thread_context: str = "",
        thread_uri: str | None = None,
    ) -> Response:
        """Generate a response to a mention"""
        # Load dynamic personality if memory is available
        if self.memory:
            try:
                dynamic_personality = await load_dynamic_personality()
                # Update the agent's system prompt with enhanced personality
                self.agent._system_prompt = dynamic_personality
                # Successfully loaded dynamic personality
            except Exception as e:
                logger.warning(f"Could not load dynamic personality: {e}")

        # Build the full prompt with thread context
        prompt_parts = []

        if thread_context and thread_context != "No previous messages in this thread.":
            prompt_parts.append(thread_context)
            prompt_parts.append("\nNew message:")

        prompt_parts.append(f"{author_handle} said: {mention_text}")

        prompt = "\n".join(prompt_parts)

        logger.info(
            f"🤖 Processing mention from @{author_handle}: {mention_text[:50]}{'...' if len(mention_text) > 50 else ''}"
        )

        # Create context for dependency injection
        context: ConversationContext = {
            "thread_uri": thread_uri,
            "author_handle": author_handle,
        }

        # Run agent with context
        result = await self.agent.run(prompt, deps=context)

        # Log action taken at info level
        if result.output.action != "reply":
            logger.info(f"🎯 Action: {result.output.action} - {result.output.reason}")

        return result.output
