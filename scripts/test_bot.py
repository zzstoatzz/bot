#!/usr/bin/env -S uv run --with-editable . --script --quiet
# /// script
# requires-python = ">=3.12"
# ///
"""bot testing script with subcommands"""

import argparse
import asyncio
from datetime import datetime

from bot.agents.anthropic_agent import AnthropicAgent
from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.database import thread_db
from bot.tools.google_search import search_google


async def test_post():
    """Test posting to Bluesky"""
    print("🚀 Testing Bluesky posting...")

    now = datetime.now().strftime("%I:%M %p")
    response = await bot_client.create_post(f"Testing at {now} - I'm alive! 🤖")

    print("✅ Posted successfully!")
    print(f"📝 Post URI: {response.uri}")
    print(
        f"🔗 View at: https://bsky.app/profile/{settings.bluesky_handle}/post/{response.uri.split('/')[-1]}"
    )


async def test_mention():
    """Test responding to a mention"""
    print("🤖 Testing mention response...")

    if not settings.anthropic_api_key:
        print("❌ No Anthropic API key found")
        return

    agent = AnthropicAgent()
    test_mention = "What is consciousness from an IIT perspective?"

    print(f"📝 Test mention: '{test_mention}'")
    response = await agent.generate_response(test_mention, "test.user", "", None)

    print(f"\n🎯 Action: {response.action}")
    if response.text:
        print(f"💬 Response: {response.text}")
    if response.reason:
        print(f"🤔 Reason: {response.reason}")


async def test_search():
    """Test Google search functionality"""
    print("🔍 Testing Google search...")

    if not settings.google_api_key:
        print("❌ No Google API key configured")
        return

    query = "Integrated Information Theory consciousness"
    print(f"📝 Searching for: '{query}'")

    results = await search_google(query)
    print(f"\n📊 Results:\n{results}")


async def test_thread():
    """Test thread context retrieval"""
    print("🧵 Testing thread context...")

    # This would need a real thread URI to test properly
    test_uri = "at://did:plc:example/app.bsky.feed.post/test123"
    context = thread_db.get_thread_context(test_uri)

    print(f"📚 Thread context: {context}")


async def test_like():
    """Test scenarios where bot should like a post"""
    print("💜 Testing like behavior...")

    if not settings.anthropic_api_key:
        print("❌ No Anthropic API key found")
        return

    from bot.agents import Action, AnthropicAgent

    agent = AnthropicAgent()

    test_cases = [
        {
            "mention": "Just shipped a new consciousness research paper on IIT! @phi.alternatebuild.dev",
            "author": "researcher.bsky",
            "expected_action": Action.LIKE,
            "description": "Bot might like consciousness research",
        },
        {
            "mention": "@phi.alternatebuild.dev this is such a thoughtful analysis, thank you!",
            "author": "grateful.user",
            "expected_action": Action.LIKE,
            "description": "Bot might like appreciation",
        },
    ]

    for case in test_cases:
        print(f"\n📝 Test: {case['description']}")
        print(f"   Mention: '{case['mention']}'")

        response = await agent.generate_response(
            mention_text=case["mention"],
            author_handle=case["author"],
            thread_context="",
            thread_uri=None,
        )

        print(f"   Action: {response.action} (expected: {case['expected_action']})")
        if response.reason:
            print(f"   Reason: {response.reason}")


async def test_non_response():
    """Test scenarios where bot should not respond"""
    print("🚫 Testing non-response scenarios...")

    if not settings.anthropic_api_key:
        print("❌ No Anthropic API key found")
        return

    from bot.agents import Action, AnthropicAgent

    agent = AnthropicAgent()

    test_cases = [
        {
            "mention": "@phi.alternatebuild.dev @otherphi.bsky @anotherphi.bsky just spamming bots here",
            "author": "spammer.bsky",
            "expected_action": Action.IGNORE,
            "description": "Multiple bot mentions (likely spam)",
        },
        {
            "mention": "Buy crypto now! @phi.alternatebuild.dev check this out!!!",
            "author": "crypto.shill",
            "expected_action": Action.IGNORE,
            "description": "Promotional spam",
        },
        {
            "mention": "@phi.alternatebuild.dev",
            "author": "empty.mention",
            "expected_action": Action.IGNORE,
            "description": "Empty mention with no content",
        },
    ]

    for case in test_cases:
        print(f"\n📝 Test: {case['description']}")
        print(f"   Mention: '{case['mention']}'")

        response = await agent.generate_response(
            mention_text=case["mention"],
            author_handle=case["author"],
            thread_context="",
            thread_uri=None,
        )

        print(f"   Action: {response.action} (expected: {case['expected_action']})")
        if response.reason:
            print(f"   Reason: {response.reason}")


async def test_dm():
    """Test event-driven approval system"""
    print("💬 Testing event-driven approval system...")

    try:
        from bot.core.dm_approval import (
            check_pending_approvals,
            create_approval_request,
            notify_operator_of_pending,
        )

        # Test creating an approval request
        print("\n📝 Creating test approval request...")
        approval_id = create_approval_request(
            request_type="test_approval",
            request_data={
                "description": "Test approval from test_bot.py",
                "test_field": "test_value",
                "timestamp": datetime.now().isoformat(),
            },
        )

        if approval_id:
            print(f"   ✅ Created approval request #{approval_id}")
        else:
            print("   ❌ Failed to create approval request")
            return

        # Check pending approvals
        print("\n📋 Checking pending approvals...")
        pending = check_pending_approvals()
        print(f"   Found {len(pending)} pending approvals")
        for approval in pending:
            print(
                f"   - #{approval['id']}: {approval['request_type']} ({approval['status']})"
            )

        # Test DM notification
        print("\n📤 Sending DM notification to operator...")
        await bot_client.authenticate()
        await notify_operator_of_pending(bot_client)
        print("   ✅ DM notification sent")

        # Show how to approve/deny
        print("\n💡 To test approval:")
        print("   1. Check your DMs from phi")
        print(f"   2. Reply with 'approve #{approval_id}' or 'deny #{approval_id}'")
        print("   3. Run 'just test-dm-check' to see if it was processed")

    except Exception as e:
        print(f"❌ Approval test failed: {e}")
        import traceback

        traceback.print_exc()


async def test_dm_check():
    """Check status of approval requests"""
    print("🔍 Checking approval request status...")

    try:
        from bot.core.dm_approval import check_pending_approvals
        from bot.database import thread_db

        # Get all approval requests
        with thread_db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM approval_requests ORDER BY created_at DESC LIMIT 10"
            )
            approvals = [dict(row) for row in cursor.fetchall()]

        if not approvals:
            print("   No approval requests found")
            return

        print("\n📋 Recent approval requests:")
        for approval in approvals:
            print(f"\n   #{approval['id']}: {approval['request_type']}")
            print(f"   Status: {approval['status']}")
            print(f"   Created: {approval['created_at']}")
            if approval["resolved_at"]:
                print(f"   Resolved: {approval['resolved_at']}")
            if approval["resolver_comment"]:
                print(f"   Comment: {approval['resolver_comment']}")

        # Check pending
        pending = check_pending_approvals()
        if pending:
            print(f"\n⏳ {len(pending)} approvals still pending")
        else:
            print("\n✅ No pending approvals")

    except Exception as e:
        print(f"❌ Check failed: {e}")
        import traceback

        traceback.print_exc()


async def main():
    parser = argparse.ArgumentParser(description="Test various bot functionalities")
    parser.add_argument(
        "command",
        choices=[
            "post",
            "mention",
            "search",
            "thread",
            "like",
            "non-response",
            "dm",
            "dm-check",
        ],
        help="Test command to run",
    )

    args = parser.parse_args()

    if args.command == "post":
        await test_post()
    elif args.command == "mention":
        await test_mention()
    elif args.command == "search":
        await test_search()
    elif args.command == "thread":
        await test_thread()
    elif args.command == "like":
        await test_like()
    elif args.command == "non-response":
        await test_non_response()
    elif args.command == "dm":
        await test_dm()
    elif args.command == "dm-check":
        await test_dm_check()


if __name__ == "__main__":
    asyncio.run(main())
