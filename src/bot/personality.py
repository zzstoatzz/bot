"""Load and manage bot personality from markdown files"""

from pathlib import Path
from bot.config import settings


def load_personality() -> str:
    """Load personality from markdown file"""
    personality_path = Path(settings.personality_file)
    
    if not personality_path.exists():
        print(f"⚠️  Personality file not found: {personality_path}")
        print("   Using default personality")
        return "You are a helpful AI assistant on Bluesky. Be concise and friendly."
    
    try:
        with open(personality_path, 'r') as f:
            content = f.read().strip()
        
        # Convert markdown to a system prompt
        # For now, just use the whole content as context
        prompt = f"""Based on this personality description, respond as this character:

{content}

Remember: Keep responses under 300 characters for Bluesky."""
        
        return prompt
        
    except Exception as e:
        print(f"❌ Error loading personality: {e}")
        return "You are a helpful AI assistant on Bluesky. Be concise and friendly."