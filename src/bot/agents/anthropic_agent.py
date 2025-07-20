"""Anthropic agent for generating responses"""

import os
from typing import Optional
from pydantic_ai import Agent
from pydantic import BaseModel, Field

from bot.config import settings


class Response(BaseModel):
    """Bot response"""
    text: str = Field(description="Response text (max 300 chars)")


class AnthropicAgent:
    """Agent that uses Anthropic Claude for responses"""
    
    def __init__(self):
        if settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        
        self.agent = Agent(
            'anthropic:claude-3-5-haiku-latest',
            system_prompt="""You are a friendly AI assistant on Bluesky.
Keep responses concise (under 300 characters).
Be conversational and natural.
Don't use @mentions in replies.""",
            result_type=Response
        )
    
    async def generate_response(self, mention_text: str, author_handle: str) -> str:
        """Generate a response to a mention"""
        prompt = f"{author_handle} said: {mention_text}"
        result = await self.agent.run(prompt)
        return result.data.text[:300]