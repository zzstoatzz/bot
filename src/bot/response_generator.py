"""Response generation for the bot"""

import logging
import random

from bot.agents._personality import load_dynamic_personality, load_personality
from bot.config import settings
from bot.memory import MemoryType
from bot.status import bot_status
from bot.ui.context_capture import context_capture

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
        self, mention_text: str, author_handle: str, thread_context: str = "", thread_uri: str | None = None
    ):
        """Generate a response to a mention"""
        # Capture context components for visualization
        components = []
        
        # 1. Base personality (always present)
        base_personality = load_personality()
        components.append({
            "name": "Base Personality",
            "type": "personality",
            "content": base_personality,
            "metadata": {"source": "personalities/phi.md"}
        })
        
        # Enhance thread context with memory if available
        enhanced_context = thread_context

        if self.memory and self.agent:
            try:
                # 2. Dynamic personality memories
                dynamic_personality = await load_dynamic_personality()
                components.append({
                    "name": "Dynamic Personality",
                    "type": "personality", 
                    "content": dynamic_personality,
                    "metadata": {"source": "TurboPuffer core memories"}
                })
                
                # Store the incoming message
                await self.memory.store_user_memory(
                    author_handle,
                    f"User said: {mention_text}",
                    MemoryType.CONVERSATION,
                )

                # Build conversation context with semantic search
                memory_context = await self.memory.build_conversation_context(
                    author_handle, include_core=True, query=mention_text
                )
                enhanced_context = f"{thread_context}\n\n{memory_context}".strip()
                logger.info("📚 Enhanced context with memories")
                
                # 3. User-specific memories (if any)
                user_memories = await self.memory.build_conversation_context(author_handle, include_core=False, query=mention_text)
                if user_memories and user_memories.strip():
                    components.append({
                        "name": f"User Memories (@{author_handle})",
                        "type": "memory",
                        "content": user_memories,
                        "metadata": {"user": author_handle, "source": "TurboPuffer user namespace"}
                    })

            except Exception as e:
                logger.warning(f"Memory enhancement failed: {e}")

        # 4. Thread context (if available)
        if thread_context and thread_context != "No previous messages in this thread.":
            components.append({
                "name": "Thread Context",
                "type": "thread",
                "content": thread_context,
                "metadata": {"thread_uri": thread_uri}
            })

        # 5. Current mention
        components.append({
            "name": "Current Mention",
            "type": "mention",
            "content": f"@{author_handle} said: {mention_text}",
            "metadata": {"author": author_handle, "thread_uri": thread_uri}
        })

        if self.agent:
            response = await self.agent.generate_response(
                mention_text, author_handle, enhanced_context, thread_uri
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

            # Capture context for visualization
            response_text = response.text if hasattr(response, 'text') else str(response.get('text', '[no text]'))
            context_capture.capture_response_context(
                mention_text=mention_text,
                author_handle=author_handle,
                thread_uri=thread_uri,
                generated_response=response_text,
                components=components
            )

            return response
        else:
            # Return a simple dict for placeholder responses
            placeholder_text = random.choice(PLACEHOLDER_RESPONSES)
            
            # Still capture context for placeholders
            context_capture.capture_response_context(
                mention_text=mention_text,
                author_handle=author_handle,
                thread_uri=thread_uri,
                generated_response=placeholder_text,
                components=components
            )
            
            return {"action": "reply", "text": placeholder_text}
