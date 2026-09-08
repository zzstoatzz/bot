"""Blog tools — greengale publishing."""

from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.core.override import get_override, refusal_text
from bot.tools._helpers import PhiDeps
from bot.tools.posting import _policy_gate
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
                # dict() wraps DotDict → plain dict so .get() works normally
                val = dict(rec.value)
                title = val.get("title", "untitled")
                rkey = rec.uri.split("/")[-1]
                published = val.get("publishedAt", "")
                tags = val.get("tags", [])
                url = f"https://greengale.app/{handle}/{rkey}"
                tag_str = f" [{', '.join(tags)}]" if tags else ""
                date_str = f" ({published[:10]})" if published else ""
                # include the AT-URI explicitly so the model doesn't have to guess
                # the collection name when passing to pub_get_document.
                lines.append(
                    f"- {title}{tag_str}{date_str}\n  uri: {rec.uri}\n  cid: {rec.cid}\n  url: {url}"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"failed to list blog posts: {e}"

    @agent.tool
    async def publish_blog_post(
        ctx: RunContext[PhiDeps],
        title: str,
        content: str,
        tags: list[str] | None = None,
        uri: Annotated[
            str | None,
            Field(
                description="Existing own blog AT-URI to revise; omit for a new article."
            ),
        ] = None,
        expected_cid: Annotated[
            str | None,
            Field(
                description="CID of the article revision you read; required with uri to prevent overwriting newer edits."
            ),
        ] = None,
    ) -> str:
        """Publish a markdown blog post to greengale.app (your ATProto blog).

        IMPORTANT: before calling this, use list_blog_posts to review your existing posts
        so you don't repeat yourself.

        To correct an existing article, read it first and supply its uri and
        expected_cid with the complete revised title and body. The URL stays fixed.
        Omitted tags preserve existing tags on revisions.

        title: post title.
        content: full markdown body.
        tags: optional list of topic tags.
        """
        if bool(uri) != bool(expected_cid):
            return "refused: revision requires both uri and expected_cid"
        override = await get_override()
        if override["active"]:
            return refusal_text(override)
        refusal, _ = await _policy_gate(
            f"publish blog title: {title}\nbody:\n{content}",
            "Phi proposes a public blog document.",
            unprompted=True,
            tool="publish_blog_post",
        )
        if refusal:
            return refusal
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

            if uri:
                return _revise_blog_document(did, handle, uri, expected_cid, doc, tags)

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
                    val = dict(rec.value)
                    existing_title = val.get("title", "")
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


def _revise_blog_document(did, handle, uri, expected_cid, doc, tags):
    """Replace a checked own document without changing its publication identity."""
    prefix = f"at://{did}/app.greengale.document/"
    if (
        not uri.startswith(prefix)
        or not uri[len(prefix) :]
        or "/" in uri[len(prefix) :]
    ):
        return "refused: target must be an existing blog document on your own repo"
    rkey = uri[len(prefix) :]
    repo = bot_client.client.com.atproto.repo
    existing = repo.get_record(
        params={"repo": did, "collection": "app.greengale.document", "rkey": rkey}
    )
    if existing.cid != expected_cid:
        return "refused: article changed since you read it; read the current revision before editing"
    record = dict(existing.value)
    record.update(title=doc.title, content=doc.content)
    if tags is not None:
        record["tags"] = tags
    repo.put_record(
        data={
            "repo": did,
            "collection": "app.greengale.document",
            "rkey": rkey,
            "record": record,
            "swap_record": expected_cid,
        }
    )
    return f"updated: https://greengale.app/{handle}/{rkey}"
