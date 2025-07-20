"""Anthropic agent for generating responses"""

import os
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from bot.config import settings
from bot.personality import load_personality
from bot.tools.google_search import GoogleSearchTool


class Response(BaseModel):
    """Bot response"""

    text: str = Field(description="Response text (max 300 chars)")


class AnthropicAgent:
    """Agent that uses Anthropic Claude for responses"""

    def __init__(self):
        if settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

        self.search_tool = GoogleSearchTool() if settings.google_api_key else None

        self.agent = Agent(
            "anthropic:claude-3-5-haiku-latest",
            system_prompt=load_personality(),
            output_type=Response,
        )

        # Register search tool if available
        if self.search_tool:

            @self.agent.tool
            async def search_web(ctx: RunContext[None], query: str) -> str:
                """Search the web for information"""
                results = await self.search_tool.search(query, num_results=3)
                return self.search_tool.format_results(results)

    async def generate_response(
        self, mention_text: str, author_handle: str, thread_context: str = ""
    ) -> str:
        """Generate a response to a mention"""
        # Build the full prompt with thread context
        prompt_parts = []

        if thread_context and thread_context != "No previous messages in this thread.":
            prompt_parts.append(thread_context)
            prompt_parts.append("\nNew message:")

        prompt_parts.append(f"{author_handle} said: {mention_text}")

        prompt = "\n".join(prompt_parts)

        # Add search capability hint if available
        if self.search_tool:
            prompt += "\n\n(You can search the web if needed to answer questions about current events or facts)"

        result = await self.agent.run(prompt)
        return result.output.text[:300]
