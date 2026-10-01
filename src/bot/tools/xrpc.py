"""Tools for atproto apps beyond Bluesky: read a lexicon, call a method."""

import json
from typing import Annotated, Any

import logfire
from pydantic import Field
from pydantic_ai import RunContext

from bot.core.override import get_override, refusal_text
from bot.core.xrpc import (
    call_method,
    enabled_methods,
    fetch_lexicon,
    service_for,
    split_nsid,
)
from bot.tools._helpers import PhiDeps

MAX_SCHEMA_CHARS = 30_000


def register(agent):
    @agent.tool
    async def describe_lexicon(
        ctx: RunContext[PhiDeps],
        nsid: Annotated[
            str,
            Field(
                description=(
                    "The lexicon to read, e.g. town.delve.membership.join. Add "
                    "#name for one definition, e.g. town.delve.membership.defs#membership."
                )
            ),
        ],
    ) -> str:
        """Read the published schema for any atproto record, query, or procedure.

        Resolves the NSID to the repo its authors publish lexicons from and
        returns the schema they wrote: a record's fields, or a method's
        parameters, input, output, and named errors. Read this before writing
        a record or calling a method in a namespace you have not used.
        """
        try:
            name, fragment = split_nsid(nsid)
            lexicon = await fetch_lexicon(name)
        except (ValueError, LookupError) as e:
            return f"could not read lexicon {nsid!r}: {e}"

        defs = lexicon["schema"].get("defs") or {}
        if fragment:
            if fragment not in defs:
                return (
                    f"{name} has no definition {fragment!r}; it defines {sorted(defs)}"
                )
            lexicon = {
                **lexicon,
                "schema": {"id": name, "defs": {fragment: defs[fragment]}},
            }
        text = json.dumps(lexicon, ensure_ascii=False)
        if len(text) > MAX_SCHEMA_CHARS:
            return (
                f"{name} is {len(text)} chars. Read one definition at a time "
                f"with {name}#name. It defines {sorted(defs)}"
            )
        return text

    @agent.tool
    async def call_xrpc(
        ctx: RunContext[PhiDeps],
        nsid: Annotated[
            str,
            Field(
                description="The query or procedure to call, e.g. town.delve.membership.getMembership."
            ),
        ],
        arguments: Annotated[
            dict[str, Any] | None,
            Field(
                description=(
                    "A query's parameters or a procedure's JSON input, as its "
                    "lexicon defines them. Omit when it takes none."
                )
            ),
        ] = None,
    ) -> str:
        """Call a method on an atproto app outside Bluesky, as yourself.

        A query reads your own state on that app (membership, notifications).
        A procedure changes it: joining, withdrawing, marking notifications seen.
        Your PDS forwards the call to the app's service and signs it as you.
        Read the method with describe_lexicon first so the arguments match its
        schema and you know its named errors.

        Works for the methods the operator has enabled; the refusal for any
        other lists them. Records in those apps are ordinary repo records,
        written with the pdsx record tools.
        """
        try:
            name, _ = split_nsid(nsid)
        except ValueError as e:
            return str(e)
        service = service_for(name)
        if service is None:
            return (
                f"{name} is not one of the methods enabled for call_xrpc. Nothing "
                f"was called. Enabled: {', '.join(enabled_methods())}. The operator "
                "adds a method; ask with report_operator."
            )
        override = await get_override()
        if override["active"]:
            return refusal_text(override)
        try:
            result = await call_method(name, arguments, service)
        except LookupError as e:
            return f"could not call {name}: {e}"
        if result["kind"] == "procedure":
            logfire.info(
                "call_xrpc procedure {nsid} via {service}: {status}",
                nsid=name,
                service=service,
                status=result["status"],
                ok=result["ok"],
                arguments=arguments,
            )
        return json.dumps(
            {"nsid": name, "service": service, **result}, ensure_ascii=False
        )
