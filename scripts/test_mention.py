#!/usr/bin/env python3
"""Test script to mention the bot and see if it responds"""

import asyncio
from datetime import datetime
from atproto import Client
import os


async def test_mention():
    """Create a post that mentions the bot"""
    # Use a different account to mention the bot
    test_handle = os.getenv("TEST_BLUESKY_HANDLE", "your-test-account.bsky.social")
    test_password = os.getenv("TEST_BLUESKY_PASSWORD", "your-test-password")
    bot_handle = os.getenv("BLUESKY_HANDLE", "zzstoatzz.bsky.social")
    
    if test_handle == "your-test-account.bsky.social":
        print("⚠️  Please set TEST_BLUESKY_HANDLE and TEST_BLUESKY_PASSWORD in .env")
        print("   (Use a different account than the bot account)")
        return
    
    client = Client()
    
    print(f"Logging in as {test_handle}...")
    client.login(test_handle, test_password)
    
    mention_text = f"Hey @{bot_handle} are you there? Testing at {datetime.now().strftime('%H:%M:%S')}"
    
    print(f"Creating post: {mention_text}")
    response = client.send_post(text=mention_text)
    
    print(f"✅ Posted mention!")
    print(f"URI: {response.uri}")
    print(f"\nThe bot should reply within ~10 seconds if it's running")
    print(f"Check: https://bsky.app/profile/{test_handle}/post/{response.uri.split('/')[-1]}")


if __name__ == "__main__":
    asyncio.run(test_mention())