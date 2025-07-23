"""Internal personality loading for agents"""

import asyncio
import logging
import os
from pathlib import Path

from bot.config import settings
from bot.memory import NamespaceMemory

logger = logging.getLogger(__name__)


def load_personality() -> str:
    """Load personality from file and dynamic memory"""
    # Start with file-based personality as base
    personality_path = Path(settings.personality_file)
    
    base_content = ""
    if personality_path.exists():
        try:
            base_content = personality_path.read_text().strip()
        except Exception as e:
            logger.error(f"Error loading personality file: {e}")
    
    # Try to enhance with dynamic memory if available
    if settings.turbopuffer_api_key and os.getenv("OPENAI_API_KEY"):
        try:
            # Create memory instance synchronously for now
            memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)
            
            # Get core memories synchronously (blocking for initial load)
            loop = asyncio.new_event_loop()
            core_memories = loop.run_until_complete(memory.get_core_memories())
            loop.close()
            
            # Build personality from memories
            personality_sections = []
            
            # Add base content if any
            if base_content:
                personality_sections.append(base_content)
            
            # Add dynamic personality sections
            for mem in core_memories:
                if mem.memory_type.value == "personality":
                    label = mem.metadata.get("label", "")
                    if label:
                        personality_sections.append(f"## {label}\n{mem.content}")
                    else:
                        personality_sections.append(mem.content)
            
            final_personality = "\n\n".join(personality_sections)
            
        except Exception as e:
            logger.warning(f"Could not load dynamic personality: {e}")
            final_personality = base_content
    else:
        final_personality = base_content
    
    # Always add handle and length reminder
    if final_personality:
        return f"{final_personality}\n\nRemember: My handle is @{settings.bluesky_handle}. Keep responses under 300 characters for Bluesky."
    else:
        return f"I am a bot on Bluesky. My handle is @{settings.bluesky_handle}. I keep responses under 300 characters."
