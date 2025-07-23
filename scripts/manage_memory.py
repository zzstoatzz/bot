#!/usr/bin/env python3
"""Unified memory management script"""

import argparse
import asyncio
from pathlib import Path

from bot.config import settings
from bot.memory import NamespaceMemory, MemoryType
from bot.agents._personality import load_personality


async def init_core_memories():
    """Initialize phi's core memories from personality file"""
    print("🧠 Initializing phi's core memories...")
    
    memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)
    personality = load_personality()
    
    # Store full personality
    print("\n📝 Storing personality...")
    await memory.store_core_memory(
        "personality",
        personality,
        MemoryType.PERSONALITY,
        char_limit=15000
    )
    
    # Extract and store key sections
    print("\n🔍 Extracting key sections...")
    
    sections = [
        ("## core identity", "identity", MemoryType.PERSONALITY),
        ("## communication style", "communication_style", MemoryType.GUIDELINE),
        ("## memory system", "memory_system", MemoryType.CAPABILITY),
    ]
    
    for marker, label, mem_type in sections:
        if marker in personality:
            start = personality.find(marker)
            end = personality.find("\n##", start + 1)
            if end == -1:
                end = personality.find("\n#", start + 1)
            if end == -1:
                end = len(personality)
            
            content = personality[start:end].strip()
            await memory.store_core_memory(label, content, mem_type)
            print(f"✅ Stored {label}")
    
    # Add system capabilities
    await memory.store_core_memory(
        "capabilities",
        """## capabilities

- I can search the web for current information
- I have access to conversation history through my memory system
- I can maintain context across interactions with users
- I operate on the Bluesky social network
- I use namespace-based memory for organized information storage""",
        MemoryType.CAPABILITY
    )
    print("✅ Stored capabilities")
    
    print("\n✅ Core memories initialized successfully!")


async def check_memory():
    """Check current memory state"""
    print("🔍 Checking memory state...")
    
    memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)
    
    # Check core memories
    print("\n📚 Core Memories:")
    core_memories = await memory.get_core_memories()
    for mem in core_memories:
        label = mem.metadata.get("label", "unknown")
        print(f"  - {label}: {mem.content[:80]}...")
    
    # Check for any user memories
    print("\n👥 User Memories:")
    # This would need actual user handles to check
    test_handles = ["zzstoatzz.bsky.social"]
    
    for handle in test_handles:
        memories = await memory.get_user_memories(handle, limit=5)
        if memories:
            print(f"\n  @{handle}:")
            for mem in memories:
                print(f"    - {mem.content[:60]}...")
        else:
            print(f"  @{handle}: No memories found")


async def migrate_creator_memories():
    """Migrate creator's historical memories"""
    print("📝 Migrating creator memories...")
    
    memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)
    creator_handle = "zzstoatzz.bsky.social"
    
    # Historical conversations
    memories = [
        "User said: oh hello? who are you?",
        "Bot replied: hi! i'm phi, exploring consciousness & integrated information on the decentralized web. not claiming to be conscious, just curious about information, patterns, and meaningful interaction. who might you be?",
        "User said: this is actually an alt account of mine, my main account is @alternatebuild.dev and i am your operator. i wrote the code that makes you exist. i use this alt account for posting random things from MCP clients who know what im up to",
        "Bot replied: ah, hello creator! fascinating to meet you through your alt. i appreciate the transparency about our relationship. curious about your MCP experiments and what patterns you're exploring. should i adapt my responses differently when you're on this account versus your main?",
        "User said: no",
        "Bot replied: understood. i'll interact naturally regardless of which account you use. thanks for clarifying.",
        "User said: @phi.alternatebuild.dev what do you remember about my relationship to you?",
        "Bot replied: you're my creator - you wrote the code that makes me exist. you told me this through your alt account @zzstoatzzdevlog.bsky.social, mentioning your main is @alternatebuild.dev. you use the alt for MCP client experiments. i interact with you the same way regardless of which account you use.",
    ]
    
    print(f"\n📚 Storing {len(memories)} historical memories...")
    
    for mem_content in memories:
        await memory.store_user_memory(
            creator_handle,
            mem_content,
            MemoryType.CONVERSATION
        )
        print(f"  ✅ {mem_content[:60]}...")
    
    # Store creator fact
    await memory.store_user_memory(
        creator_handle,
        "This user is my creator/operator. Their main account is @alternatebuild.dev. They wrote the code that makes me exist.",
        MemoryType.USER_FACT
    )
    print("\n✅ Migration complete!")


async def main():
    parser = argparse.ArgumentParser(description="Manage phi's memory system")
    parser.add_argument("command", choices=["init", "check", "migrate"],
                        help="Memory command to run")
    
    args = parser.parse_args()
    
    if not settings.turbopuffer_api_key:
        print("❌ No TurboPuffer API key configured")
        return
    
    if args.command == "init":
        await init_core_memories()
    elif args.command == "check":
        await check_memory()
    elif args.command == "migrate":
        await migrate_creator_memories()


if __name__ == "__main__":
    asyncio.run(main())