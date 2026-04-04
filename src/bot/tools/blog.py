"""Blog tools — greengale publishing."""

from pydantic_ai import RunContext

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.tools._helpers import PhiDeps
from bot.types import GreenGaleDocument, generate_tid


def register(agent):
    @agent.tool
    async def list_blog_posts(ctx: RunContext[PhiDeps], limit: int = 10) -> str:
        """List your published blog posts on greengale. Call this before publishing to avoid duplicates."""
        try:
            await bot_client.authenticate()
            assert bot_client.client.me is not None
            did = bot_client.client.me.did
            handle = settings.bluesky_handle

            response = bot_client.client.com.atproto.repo.list_records(
                params={
                    "repo": did,
                    "collection": "app.greengale.document",
                    "limit": min(limit, 100),
                }
            )

            if not response.records:
                return "no blog posts yet"

            lines = []
            for rec in response.records:
                val = rec.value
                title = (
                    val.get("title", "untitled")
                    if isinstance(val, dict)
                    else "untitled"
                )
                rkey = rec.uri.split("/")[-1]
                published = val.get("publishedAt", "") if isinstance(val, dict) else ""
                tags = val.get("tags", []) if isinstance(val, dict) else []
                url = f"https://greengale.app/{handle}/{rkey}"
                tag_str = f" [{', '.join(tags)}]" if tags else ""
                date_str = f" ({published[:10]})" if published else ""
                lines.append(f"- {title}{tag_str}{date_str}\n  {url}")
            return "\n".join(lines)
        except Exception as e:
            return f"failed to list blog posts: {e}"

    @agent.tool
    async def publish_blog_post(
        ctx: RunContext[PhiDeps],
        title: str,
        content: str,
        tags: list[str] | None = None,
    ) -> str:
        """Publish a markdown blog post to greengale.app (your ATProto blog).

        IMPORTANT: before calling this, use list_blog_posts to review your existing posts
        so you don't repeat yourself.

        title: post title.
        content: full markdown body.
        tags: optional list of topic tags.
        """
        try:
            doc = GreenGaleDocument(
                title=title,
                content=content,
                tags=tags or [],
            )
        except Exception as e:
            return f"validation failed: {e}"

        try:
            await bot_client.authenticate()
            assert bot_client.client.me is not None
            did = bot_client.client.me.did
            handle = settings.bluesky_handle

            # check for title duplicates
            existing = bot_client.client.com.atproto.repo.list_records(
                params={
                    "repo": did,
                    "collection": "app.greengale.document",
                    "limit": 100,
                }
            )
            if existing.records:
                for rec in existing.records:
                    val = rec.value
                    existing_title = (
                        val.get("title", "") if isinstance(val, dict) else ""
                    )
                    if existing_title == title:
                        rkey = rec.uri.split("/")[-1]
                        return (
                            f"refused: a post with this exact title already exists "
                            f"at https://greengale.app/{handle}/{rkey}"
                        )

            rkey = generate_tid()
            record = doc.to_record(handle=handle, rkey=rkey)

            bot_client.client.com.atproto.repo.put_record(
                data={
                    "repo": did,
                    "collection": "app.greengale.document",
                    "rkey": rkey,
                    "record": record,
                }
            )

            url = f"https://greengale.app/{handle}/{rkey}"

            # store in episodic memory
            if ctx.deps.memory:
                await ctx.deps.memory.store_episodic_memory(
                    f"published blog post: {title} — {url}",
                    ["blog", "greengale"] + (tags or []),
                    source="tool",
                )

            return f"published: {url}"
        except Exception as e:
            return f"failed to publish: {e}"
