#!/usr/bin/env python3
"""Test script to verify posting capabilities"""

import asyncio
from datetime import datetime

from atproto import Client

from bot.config import settings


async def test_post():
    """Test creating a post on Bluesky"""
    client = Client(base_url=settings.bluesky_service)

    print(f"Logging in as {settings.bluesky_handle}...")
    client.login(settings.bluesky_handle, settings.bluesky_password)

    test_text = f"Test post from bot at {datetime.now().isoformat()} 🤖"

    print(f"Creating post: {test_text}")
    # Use the simpler send_post method
    response = client.send_post(text=test_text)

    post_uri = response.uri
    print("✅ Post created successfully!")
    print(f"URI: {post_uri}")
    print(
        f"View at: https://bsky.app/profile/{settings.bluesky_handle}/post/{post_uri.split('/')[-1]}"
    )

    return post_uri


async def test_reply(post_uri: str):
    """Test replying to a post"""
    client = Client(base_url=settings.bluesky_service)
    client.login(settings.bluesky_handle, settings.bluesky_password)

    # Get the post we're replying to
    parent_post = client.app.bsky.feed.get_posts(params={"uris": [post_uri]})
    if not parent_post.posts:
        raise ValueError("Parent post not found")

    # Build reply reference
    from atproto import models

    parent_cid = parent_post.posts[0].cid
    parent_ref = models.ComAtprotoRepoStrongRef.Main(uri=post_uri, cid=parent_cid)
    reply_ref = models.AppBskyFeedPost.ReplyRef(parent=parent_ref, root=parent_ref)

    reply_text = "This is a test reply from the bot 🔄"

    print(f"Creating reply: {reply_text}")
    # Use send_post with reply_to
    response = client.send_post(text=reply_text, reply_to=reply_ref)

    print("✅ Reply created successfully!")
    print(f"URI: {response.uri}")


async def main():
    """Run all tests"""
    print("🧪 Testing Bluesky posting capabilities...\n")

    try:
        # Test creating a post
        post_uri = await test_post()

        print("\nWaiting 2 seconds before replying...")
        await asyncio.sleep(2)

        # Test replying to the post
        await test_reply(post_uri)

        print("\n✨ All tests passed!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
