"""Internal personality loading for agents"""

import logging
import os
from pathlib import Path

from bot.config import settings
from bot.memory import NamespaceMemory

logger = logging.getLogger(__name__)


def load_personality() -> str:
    """Load base personality from file"""
    personality_path = Path(settings.personality_file)
    
    base_content = ""
    if personality_path.exists():
        try:
            base_content = personality_path.read_text().strip()
        except Exception as e:
            logger.error(f"Error loading personality file: {e}")
    
    if base_content:
        return f"{base_content}\n\nRemember: My handle is @{settings.bluesky_handle}. Keep responses under 300 characters for Bluesky."
    else:
        return f"I am a bot on Bluesky. My handle is @{settings.bluesky_handle}. I keep responses under 300 characters for Bluesky."


async def load_dynamic_personality() -> str:
    """Load personality with focused enhancements (no duplication)"""
    # Start with base personality
    base_content = load_personality()
    
    if not (settings.turbopuffer_api_key and os.getenv("OPENAI_API_KEY")):
        return base_content
    
    try:
        memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)
        enhancements = []
        
        # Look for personality evolution (changes/growth only)
        core_memories = await memory.get_core_memories()
        for mem in core_memories:
            label = mem.metadata.get("label", "")
            # Only add evolution and current_state, not duplicates
            if label in ["evolution", "current_state"] and mem.metadata.get("type") == "personality":
                enhancements.append(f"## {label}\n{mem.content}")
        
        # Add enhancements if any
        if enhancements:
            return f"{base_content}\n\n{''.join(enhancements)}"
        else:
            return base_content
            
    except Exception as e:
        logger.warning(f"Could not load personality enhancements: {e}")
        return base_content
