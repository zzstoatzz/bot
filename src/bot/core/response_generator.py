"""Response generation - placeholder for now, easy to swap with LLM later"""

import random
from typing import Protocol


class ResponseGenerator(Protocol):
    """Protocol for response generators - makes it easy to swap implementations"""
    
    async def generate_response(self, mention_text: str, author_handle: str) -> str:
        """Generate a response to a mention"""
        ...


class PlaceholderResponseGenerator:
    """Temporary placeholder responses until LLM is integrated"""
    
    responses = [
        "🤖 beep boop! I'm still learning how to chat. Check back soon!",
        "⚙️ *whirrs mechanically* I'm a work in progress!",
        "🔧 Under construction! My neural networks are still training...",
        "📡 Signal received! But my language circuits aren't ready yet.",
        "🎯 You found me! I'm not quite ready to chat yet though.",
        "🚧 Pardon the dust - bot brain installation in progress!",
        "💭 I hear you! Just need to learn how to respond properly first...",
        "🔌 Still booting up my conversation modules!",
        "📚 Currently reading the manual on how to be a good bot...",
        "🎪 Nothing to see here yet - but stay tuned!",
    ]
    
    async def generate_response(self, mention_text: str, author_handle: str) -> str:
        """Generate a random placeholder response"""
        # Just return a random response - no need to @mention in replies
        # (Bluesky automatically notifies the person you're replying to)
        return random.choice(self.responses)


class LLMResponseGenerator:
    """Future LLM-based response generator"""
    
    def __init__(self, agent):
        self.agent = agent
    
    async def generate_response(self, mention_text: str, author_handle: str) -> str:
        """Generate response using LLM agent"""
        # TODO: Implement with pydantic-ai agent
        raise NotImplementedError("LLM integration coming soon!")


# Export the current implementation
response_generator = PlaceholderResponseGenerator()