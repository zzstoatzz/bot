"""Personality introspection tools for the agent"""

import logging
from typing import Literal

from bot.memory import NamespaceMemory
from bot.personality import add_interest, update_current_state

logger = logging.getLogger("bot.personality_tools")

PersonalitySection = Literal["interests", "current_state", "communication_style", "core_identity", "boundaries"]


async def view_personality_section(memory: NamespaceMemory, section: PersonalitySection) -> str:
    """View a section of my personality"""
    try:
        memories = await memory.get_core_memories()
        
        # Find the requested section
        for mem in memories:
            if mem.metadata.get("label") == section:
                return mem.content
                
        return f"Section '{section}' not found in my personality"
        
    except Exception as e:
        logger.error(f"Failed to view personality: {e}")
        return "Unable to access personality data"


async def reflect_on_interest(memory: NamespaceMemory, topic: str, reflection: str) -> str:
    """Reflect on a potential new interest"""
    # Check if this is genuinely interesting based on context
    if len(reflection) < 20:
        return "Need more substantial reflection to add an interest"
        
    # Add the interest
    success = await add_interest(memory, topic, reflection)
    
    if success:
        return f"Added '{topic}' to my interests based on: {reflection}"
    else:
        return "Failed to update interests"


async def update_self_reflection(memory: NamespaceMemory, reflection: str) -> str:
    """Update my current state/self-reflection"""
    if len(reflection) < 50:
        return "Reflection too brief to warrant an update"
        
    success = await update_current_state(memory, reflection)
    
    if success:
        return "Updated my current state reflection"
    else:
        return "Failed to update reflection"