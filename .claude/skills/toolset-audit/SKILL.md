---
name: toolset-audit
description: Audit an agent's toolset and skills against evidence — what each tool weighs in the context window, how often it was actually called, when it was added and under which gating paradigm — and produce a remove / filter / keep decision per tool. Use when an agent's prompt feels heavy, a toolset has grown by accretion, or before changing what an agent can do. phi-specific: the queries and paradigm dates are hers.
---

# agent toolset audit

a toolset accretes: every tool was a good idea on the day it shipped, under
the gating and consent model of that day. the audit asks three questions per
tool, each answered by a measurement, then reads the answers with suspicion
proportional to age.

## the three measurements

**1. weight** — what the definition costs in every request.

- pydantic-ai agents: `Model.count_tokens` per tool definition, marginal
  (count the request with tools[:i+1] minus tools[:i]) so the provider's
  tool-use preamble lands in its own row rather than on the first tool. phi's
  implementation: `bot/src/bot/core/context_tokens.py`; served as
  `GET /api/context/budget` and drawn on `/operator`.
- anything else: `len(json.dumps(schema)) // 4` is an estimate; label it so.

**2. usage** — how often it was called, over at least 30 days.

logfire (pydantic-ai instrumentation), `/v1/query` with a read token:

```sql
SELECT attributes->>'gen_ai.tool.name' AS tool,
       count(*) AS calls, count(DISTINCT trace_id) AS runs
FROM records
WHERE span_name = 'running tool'
GROUP BY 1 ORDER BY 2 DESC
```

MCP tool names arrive with the toolset's `tool_prefix` (`tangled_read_file`)
or without one (pdsx's `get_record`); join on both spellings. for skills,
group `load_skill` by `attributes->>'tool_arguments'` to see which skills are
ever loaded.

**3. age and paradigm** — when it was written and what gate existed then.

```bash
git log --diff-filter=A --format=%ad --date=short -- src/bot/tools/<module>.py | tail -1
git log --format=%ad --date=short -S'<server url or prefix>' -- src/bot/agent.py | tail -1
```

then list the paradigm shifts in the repo's history (phi's: consent layer and
policy judge 2026-04/05, safe-mode override 2026-07-25, own-source pull loop
2026-08-21, issues-for-gardener 2026-09-02). a tool older than a shift was
designed without it; ask whether the shift made the tool redundant
(like-as-approval tools once approval moved to merges) or unsafe (lifecycle
mutations on the operator's repos once the agent became a reviewer).

## reading the table

sort by weight descending and answer, per tool:

- **never called**: remove, unless it is a safety valve the operator wants
  standing (say which). a tool that exists "in case" costs its weight on
  every request forever.
- **called only by one skill**: it belongs behind that skill. if the skill
  was never loaded either, both go.
- **an MCP server exposing its whole surface**: filter to the verbs the agent
  used (`AbstractToolset.filtered()` in pydantic-ai; no server change). docs,
  schema, identity, and orientation tools are for people building the
  service, not for an agent watching it.
- **owner-gated tools from the earliest consent mechanic**: the live ones
  earn their keep by usage; the dead ones are the paradigm talking.
- **heavy and used**: leave the tool, but read the docstring — weight is
  mostly operating rules written into descriptions. rules that apply to
  several tools belong in the instructions once, not in each docstring.
- **overlap**: two tools with the same verb on the same object (`search_posts`
  vs `web_search` vs `pub_search`) are fine when each has a distinct source;
  suspect them when the prompt has to explain which to use.

skills get the same three questions: weight of the catalog line, loads per
month, age. a skill never loaded in 30 days is either unneeded or unfindable
from its description — decide which before deleting.

## output

a dated doc in the repo's `docs/` (phi: `docs/toolset-audit-2026-09.md`)
with: the evidence sources and window, a by-origin table, a never-called
table with the skeptical reading and a decision per row, the lightly-used
list, and the total savings if every decision were taken. decisions are the
operator's; the audit ends at the recommendation.

after changes land, the weight is visible immediately (the panel); usage
needs another month. rerun then, and compare the two tables.

## gotchas

- a tool's *absence* from usage can mean the prompt never mentions it. check
  the instructions and skills for the name before calling it dead: unfindable
  and useless look identical in the table.
- per-tool token counts that sum to more than the whole-prompt count mean the
  preamble was counted once per tool; use marginal counting.
- the audit window must cover the agent's slow cadences (weekly passes,
  monthly retros) or those tools will read as unused.
