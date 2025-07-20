#!/usr/bin/env python
"""Test thread context by simulating a conversation"""

import asyncio

from bot.database import thread_db


async def test_thread_context():
    """Test thread database and context generation"""
    print("🧪 Testing Thread Context")

    # Test thread URI
    thread_uri = "at://did:example:123/app.bsky.feed.post/abc123"

    # Add some messages
    print("\n📝 Adding messages to thread...")
    thread_db.add_message(
        thread_uri=thread_uri,
        author_handle="alice.bsky",
        author_did="did:alice",
        message_text="@phi What's your take on consciousness?",
        post_uri="at://did:alice/app.bsky.feed.post/msg1",
    )

    thread_db.add_message(
        thread_uri=thread_uri,
        author_handle="phi",
        author_did="did:bot",
        message_text="Consciousness fascinates me! It's the integration of information creating subjective experience.",
        post_uri="at://did:bot/app.bsky.feed.post/msg2",
    )

    thread_db.add_message(
        thread_uri=thread_uri,
        author_handle="bob.bsky",
        author_did="did:bob",
        message_text="@phi But how do we know if something is truly conscious?",
        post_uri="at://did:bob/app.bsky.feed.post/msg3",
    )

    # Get thread context
    print("\n📖 Thread context:")
    context = thread_db.get_thread_context(thread_uri)
    print(context)

    # Get raw messages
    print("\n🗂️  Raw messages:")
    messages = thread_db.get_thread_messages(thread_uri)
    for msg in messages:
        print(f"  - @{msg['author_handle']}: {msg['message_text'][:50]}...")

    print("\n✅ Thread context test complete!")


if __name__ == "__main__":
    asyncio.run(test_thread_context())
