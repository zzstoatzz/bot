"""Read and revise the private working notebook."""

import asyncio
import json
from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext

from bot.memory.notebook import find_pages, read_page, write_page
from bot.tools._helpers import PhiDeps


def register(agent):
    @agent.tool
    async def read_notebook(
        ctx: RunContext[PhiDeps],
        page: Annotated[
            str, Field(description="Exact page name; index is the orientation page")
        ],
        revision: Annotated[
            int | None, Field(description="Historical revision; omit for current")
        ] = None,
    ) -> str:
        """Read a working page or one of its prior revisions verbatim.

        Pages are your own revisable accounts. Their source links let you check
        them. A recorded conclusion is not evidence that an action succeeded.
        """
        result = await asyncio.to_thread(read_page, page, revision)
        if revision is None:
            current = result["page"]
            ctx.deps.run_cache[f"notebook:{page}"] = str(
                current["revision"] if current else 0
            )
        return json.dumps(result, ensure_ascii=False)

    @agent.tool
    async def find_notebook(
        ctx: RunContext[PhiDeps],
        query: Annotated[
            str,
            Field(
                description="Literal text in page names or contents; empty lists pages"
            ),
        ] = "",
        after: Annotated[
            str, Field(description="next_after from an earlier page of the same search")
        ] = "",
    ) -> str:
        """Find current notebook pages; open a match with read_notebook.

        Results are a paginated directory with short excerpts, not complete pages.
        Older revisions remain available by name and revision.
        """
        return json.dumps(
            await asyncio.to_thread(find_pages, query, after), ensure_ascii=False
        )

    @agent.tool
    async def write_notebook(
        ctx: RunContext[PhiDeps],
        page: Annotated[
            str,
            Field(
                description="Lowercase page name, e.g. people/alma or questions/river"
            ),
        ],
        content: Annotated[
            str,
            Field(
                description="Complete replacement text, including useful source references"
            ),
        ],
        expected_revision: Annotated[
            int,
            Field(
                ge=0,
                description="Current revision from read_notebook; 0 for a missing page",
            ),
        ],
    ) -> str:
        """Create a private working page or revise one after reading its current version.

        Your index is injected each run (2,500 characters); other pages are read
        on demand (12,000 characters each). Keep links to evidence and related
        pages where useful. Describe what changed or remains open in your own
        words. Past revisions survive; an empty body archives a page from search.
        Conflicts require reading the new version and reconciling your edit.
        A new page can be created with expected_revision=0 without a prior read.
        """
        if ctx.deps.private_message_context or ctx.deps.permissioned:
            return "Not written: this shared notebook cannot retain private conversation or permissioned material."
        if expected_revision != 0 and ctx.deps.run_cache.get(f"notebook:{page}") != str(
            expected_revision
        ):
            return "Read this page's current version with read_notebook before writing it. Nothing written."
        try:
            result = await asyncio.to_thread(
                write_page, page, content, expected_revision
            )
        except ValueError as error:
            return str(error)
        if result["status"] == "ok":
            ctx.deps.run_cache[f"notebook:{page}"] = str(result["revision"])
        return json.dumps(result, ensure_ascii=False)
