"""Response generation for the bot"""

import random

from bot.config import settings
from bot.status import bot_status

PLACEHOLDER_RESPONSES = [
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


class ResponseGenerator:
    """Generates responses to mentions"""

    def __init__(self):
        self.agent: object | None = None

        # Try to initialize AI agent if credentials available
        if settings.anthropic_api_key:
            try:
                from bot.agents.anthropic_agent import AnthropicAgent

                self.agent = AnthropicAgent()
                bot_status.ai_enabled = True
                print("✅ AI responses enabled (Anthropic)")
            except Exception as e:
                print(f"⚠️  Failed to initialize AI agent: {e}")
                print("   Using placeholder responses")

    async def generate(
        self, mention_text: str, author_handle: str, thread_context: str = ""
    ) -> str:
        """Generate a response to a mention"""
        if self.agent:
            return await self.agent.generate_response(
                mention_text, author_handle, thread_context
            )
        else:
            return random.choice(PLACEHOLDER_RESPONSES)
