"""Response generation for the bot"""

import logging
import os
import random

from bot.config import settings
from bot.memory import MemoryType, NamespaceMemory
from bot.status import bot_status

logger = logging.getLogger("bot.response")

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
        self.memory: object | None = None

        # Try to initialize AI agent if credentials available
        if settings.anthropic_api_key:
            try:
                from bot.agents.anthropic_agent import AnthropicAgent

                self.agent = AnthropicAgent()
                bot_status.ai_enabled = True
                logger.info("✅ AI responses enabled (Anthropic)")
                
                # Use the agent's memory if it has one
                if hasattr(self.agent, 'memory') and self.agent.memory:
                    self.memory = self.agent.memory
                    logger.info("💾 Memory system enabled (from agent)")
                else:
                    self.memory = None
            except Exception as e:
                logger.warning(f"⚠️  Failed to initialize AI agent: {e}")
                logger.warning("   Using placeholder responses")
                self.memory = None

    async def generate(
        self, mention_text: str, author_handle: str, thread_context: str = ""
    ):
        """Generate a response to a mention"""
        # Enhance thread context with memory if available
        enhanced_context = thread_context

        if self.memory and self.agent:
            try:
                # Store the incoming message
                await self.memory.store_user_memory(
                    author_handle,
                    f"User said: {mention_text}",
                    MemoryType.CONVERSATION,
                )

                # Build conversation context
                memory_context = await self.memory.build_conversation_context(
                    author_handle, include_core=True
                )
                enhanced_context = f"{thread_context}\n\n{memory_context}".strip()
                logger.info("📚 Enhanced context with memories")

            except Exception as e:
                logger.warning(f"Memory enhancement failed: {e}")

        if self.agent:
            response = await self.agent.generate_response(
                mention_text, author_handle, enhanced_context
            )

            # Store bot's response in memory if available
            if (
                self.memory
                and hasattr(response, "action")
                and response.action == "reply"
                and response.text
            ):
                try:
                    await self.memory.store_user_memory(
                        author_handle,
                        f"Bot replied: {response.text}",
                        MemoryType.CONVERSATION,
                    )
                except Exception as e:
                    logger.warning(f"Failed to store bot response: {e}")

            return response
        else:
            # Return a simple dict for placeholder responses
            return {"action": "reply", "text": random.choice(PLACEHOLDER_RESPONSES)}
