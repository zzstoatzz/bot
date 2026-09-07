"""Search tools — bluesky posts, trending, open web.

cosmik/semble network search lives in the semble MCP toolset
(semble_execute composing search_semantic and friends), not here.
"""

import json
from datetime import date
from typing import Annotated, Literal

import httpx
from pydantic import Field
from pydantic_ai import RunContext

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.core.prior_coverage import coverage_note
from bot.tools._helpers import PhiDeps, _relative_age
from bot.tools.coral import entity_page

# coral: the operator's firehose NER service (sibling repo). `/` returns its
# own endpoint list; the coral-editorial skill documents what each route is for.
CORAL_BASE = "https://coral.fly.dev"


def _day_bound(day: str) -> str:
    """YYYY-MM-DD -> the ISO instant searchPosts wants; full timestamps pass through."""
    return f"{day}T00:00:00Z" if len(day) == 10 else day


def render_posts(posts: list[dict], today: date) -> str:
    """one line per post from appview JSON: handle, likes, age, text."""
    lines = []
    for post in posts:
        text = (post.get("record") or {}).get("text", "")
        handle = (post.get("author") or {}).get("handle", "?")
        likes = post.get("likeCount") or 0
        age = _relative_age(post.get("indexedAt") or "", today)
        age_str = f", {age}" if age else ""
        lines.append(
            f"@{handle} [{post.get('uri', '')}] ({likes} likes{age_str}): {text[:200]}"
        )
    return "\n\n".join(lines)


def register(agent):
    @agent.tool
    async def search_people(
        ctx: RunContext[PhiDeps],
        query: Annotated[str, Field(description="A name or handle prefix to resolve.")],
    ) -> str:
        """Find candidate accounts through typeahead.waow.tech. Returns up to
        ten handles and DIDs. Use a resolved handle with search_memory(about=...).
        These are identity matches, not evidence of a previous encounter. If
        context cannot distinguish candidates, ask the person which they mean.
        """
        query = query.strip().lstrip("@")
        if not query:
            return "Provide a name or handle prefix."
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://typeahead.waow.tech/xrpc/tech.waow.typeahead.searchActors",
                    params={"q": query, "limit": 10},
                    headers={"X-Client": "phi.zzstoatzz.io"},
                )
                response.raise_for_status()
                actors = response.json()["actors"]
                candidates = [
                    {
                        "handle": a["handle"],
                        "did": a["did"],
                        "display_name": a.get("displayName", ""),
                    }
                    for a in actors[:10]
                ]
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return "Identity lookup unavailable. This does not establish that the person is absent."
        return json.dumps({"candidates": candidates}, ensure_ascii=False)

    @agent.tool
    async def search_posts(
        ctx: RunContext[PhiDeps],
        query: str,
        limit: int = 10,
        author: Annotated[
            str | None,
            Field(description="only posts by this handle or did."),
        ] = None,
        since: Annotated[
            str | None,
            Field(description="only posts on or after this date, YYYY-MM-DD."),
        ] = None,
        until: Annotated[
            str | None,
            Field(description="only posts before this date, YYYY-MM-DD."),
        ] = None,
        sort: Literal["top", "latest"] = "top",
        cursor: Annotated[
            str | None,
            Field(
                description="continue a previous search from the cursor it returned."
            ),
        ] = None,
    ) -> str:
        """Search Bluesky posts by keyword. author/since/until narrow the search the way the network's own search does; use them before paging through a feed by hand. Up to 100 results per call, and a cursor when there are more."""
        params: dict = {"q": query, "limit": max(1, min(limit, 100)), "sort": sort}
        if cursor:
            params["cursor"] = cursor
        if author:
            params["author"] = author.lstrip("@")
        if since:
            params["since"] = _day_bound(since)
        if until:
            params["until"] = _day_bound(until)
        try:
            page = await bot_client.search_posts_raw(params)
        except Exception as e:
            return f"search failed: {e}"
        posts = page.get("posts") or []
        if not posts:
            return f"no posts found for '{query}'"
        result = render_posts(posts, date.today())
        if page.get("cursor"):
            result += f"\n\ncursor: {page['cursor']}"
        # perception-keyed recall: seeing material triggers memory of
        # having covered it, before any decision to post is made.
        if note := await coverage_note(ctx.deps.memory, result):
            result += f"\n\n{note}"
        return result

    @agent.tool
    async def web_search(
        ctx: RunContext[PhiDeps],
        query: Annotated[
            str,
            Field(description="Search query — natural language."),
        ],
        time_range: Annotated[
            Literal["day", "week", "month", "year"] | None,
            Field(
                description=(
                    "Bound results to a time window relative to today. "
                    "Use this BEFORE asserting recency in a post — "
                    "e.g. set 'week' before claiming something happened "
                    "this week. Without it, results may include stale items."
                )
            ),
        ] = None,
        topic: Annotated[
            Literal["general", "news"] | None,
            Field(
                description=(
                    "'news' optimizes for recent journalism, 'general' for "
                    "evergreen content. Default: general."
                )
            ),
        ] = None,
        max_results: Annotated[
            int,
            Field(description="How many results to return. Default 5."),
        ] = 5,
    ) -> str:
        """Search the open web via Tavily.

        Use to ground claims about the world outside atproto — current
        events, primary sources, official statements, technical docs.
        For atproto posts use search_posts; for the cosmik network use
        the semble tools (semble_execute with search_semantic).

        IMPORTANT: if you're about to assert something is recent, current,
        or 'this week,' pass time_range first. headlines without dates
        aren't evidence of when something happened."""
        if not settings.tavily_api_key:
            return "web_search unavailable: TAVILY_API_KEY not set"

        body: dict = {
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }
        if time_range:
            body["time_range"] = time_range
        if topic:
            body["topic"] = topic

        try:
            async with httpx.AsyncClient(timeout=20) as http:
                r = await http.post(
                    "https://api.tavily.com/search",
                    headers={
                        "Authorization": f"Bearer {settings.tavily_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            return f"web search failed: {e}"

        results = data.get("results", [])
        if not results:
            return f"no web results for '{query}'"

        scope_parts = []
        if time_range:
            scope_parts.append(f"time_range={time_range}")
        if topic:
            scope_parts.append(f"topic={topic}")
        scope = f" ({', '.join(scope_parts)})" if scope_parts else ""

        lines = [f"web results for '{query}'{scope}:"]
        for i, r_item in enumerate(results, 1):
            title = r_item.get("title", "untitled")
            url = r_item.get("url", "")
            content = (r_item.get("content") or "").strip()
            lines.append("")
            lines.append(f"{i}. {title}")
            if url:
                lines.append(f"   {url}")
            if content:
                lines.append(f"   {content[:400]}")
        result = "\n".join(lines)
        if note := await coverage_note(ctx.deps.memory, result):
            result = f"{result}\n\n{note}"
        return result

    @agent.tool
    async def get_trending(ctx: RunContext[PhiDeps]) -> str:
        """Get what's currently trending on Bluesky. Returns coral's curated stories (named groups of co-occurring entities from the firehose), the entities driving them, and official Bluesky trending topics. Use this when someone asks about current events, what people are talking about, or when you want timely context. For anything deeper than this summary, use coral_query."""
        parts: list[str] = []

        async with httpx.AsyncClient(timeout=15) as client:
            # curated groups first: coral's LLM curator names clusters into
            # stories, which is denser signal than the bare entity list (and is
            # what phi's own editorialContext notes shape).
            try:
                r = await client.get(
                    f"{CORAL_BASE}/groups/history", params={"limit": 8}
                )
                r.raise_for_status()
                topics = r.json().get("topics", [])
                if topics:
                    lines = ["coral stories (curated from the firehose):"]
                    for t in topics:
                        members = ", ".join(t.get("entities", [])[:5])
                        lines.append(
                            f"  {t.get('label', '?')} — {members}"
                            f" (seen {t.get('observations', 0)}x)"
                        )
                    parts.append("\n".join(lines))
            except Exception as e:
                parts.append(f"coral stories unavailable: {e}")

            # entities second, and fewer of them: they catch a spike the curator
            # has not named yet, which is the one thing the groups cannot show.
            try:
                r = await client.get(f"{CORAL_BASE}/entity-graph")
                r.raise_for_status()
                data = r.json()
                entities = data.get("entities", [])
                stats = data.get("stats", {})

                by_trend = sorted(
                    entities, key=lambda e: e.get("trend", 0), reverse=True
                )[:8]

                lines = [
                    f"coral entities ({stats.get('active', 0)} active, "
                    f"{stats.get('clusters', 0)} clusters"
                    f"{', percolating' if stats.get('percolates') else ''}):"
                ]
                for e in by_trend:
                    lines.append(
                        f"  {e['text']} ({e.get('label', '')}) "
                        f"trend={e.get('trend', 0):.2f}"
                    )
                parts.append("\n".join(lines))
            except Exception as e:
                parts.append(f"coral unavailable: {e}")

            # official bluesky trending topics
            try:
                r = await client.get(
                    "https://public.api.bsky.app/xrpc/app.bsky.unspecced.getTrendingTopics"
                )
                r.raise_for_status()
                topics = r.json().get("topics", [])
                if topics:
                    lines = ["bluesky trending:"]
                    for t in topics[:15]:
                        lines.append(f"  {t.get('displayName', t.get('topic', ''))}")
                    parts.append("\n".join(lines))
            except Exception as e:
                parts.append(f"bluesky trending unavailable: {e}")

        return "\n\n".join(parts) if parts else "no trending data available"

    @agent.tool
    async def coral_query(
        ctx: RunContext[PhiDeps],
        path: Annotated[
            str,
            Field(
                description=(
                    "coral API path, e.g. '/groups/history?limit=20', "
                    "'/entity-graph', '/history/topics?range=day', '/stats', "
                    "or the '/simcluster/...' mirror. GET '/' for the "
                    "endpoint list."
                )
            ),
        ],
        query: Annotated[
            str,
            Field(
                description="Entity-name substring, case-insensitive; graph endpoints only."
            ),
        ] = "",
        limit: Annotated[
            int, Field(ge=1, le=20, description="Entities per graph page, 1–20.")
        ] = 20,
        offset: Annotated[
            int,
            Field(
                ge=0,
                description="Graph page offset; use next_offset from the previous result.",
            ),
        ] = 0,
    ) -> str:
        """Read any endpoint on coral, the operator's firehose entity-graph service. Use when get_trending's summary is not enough — to page further back through curated stories, pull an entity's history, or check graph health. Graph endpoints return searchable entity summaries with next_offset; use the query, limit, and offset tool arguments, not URL parameters. Load the coral-editorial skill for route details."""
        if not path.startswith("/"):
            path = "/" + path
        graph_path = path.split("?", 1)[0]
        is_graph = graph_path in {"/entity-graph", "/simcluster/entity-graph"}
        if is_graph and "?" in path:
            return "Use query, limit, and offset tool arguments for graph pages; remove URL parameters."
        if not 1 <= limit <= 20 or offset < 0:
            return "Graph limit must be 1–20 and offset must be nonnegative."
        if not is_graph and (query or limit != 20 or offset):
            return (
                "query, limit, and offset tool arguments apply only to graph endpoints."
            )
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(f"{CORAL_BASE}{path}")
                r.raise_for_status()
                if is_graph:
                    return entity_page(r.json(), query, limit, offset)
                body = r.text
        except Exception as e:
            return f"coral {path} failed: {e}"

        if len(body) > 8000:
            return (
                body[:8000]
                + f"\n\n[truncated at 8000 of {len(body)} chars — narrow the "
                "query with a limit/hours param]"
            )
        return body
