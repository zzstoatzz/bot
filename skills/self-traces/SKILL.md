---
name: self-traces
description: Query your own execution traces (logfire) to answer "what did I actually do" — every tool call, argument, error, and silent failure across all your runs. Load before using query_traces. Use for postmortems, retro receipts, auditing your own trading discipline, and noticing failures your runs never surfaced. Not for deciding what to post.
---

traces record requests, returned results, and failures. memory records your
saved account; the PDS records published objects. To check a claim, identify
the run, inspect the relevant result, and state the coverage it supports.
A tool name and its arguments establish what you requested. The returned
result establishes what you received. Neither alone establishes your motive.

## the actual situation — read this before querying

- `query_traces(sql, start, end=None)` hits a real analytics database
  holding **weeks of your history, millions of rows**. an unbounded query is
  a firehose that will blow out your context. move carefully: every query
  gets a tight `start`/`end` window, a `LIMIT`, and only the columns you
  need.
- the time window comes from the `start`/`end` tool arguments (ISO 8601),
  not from SQL — a `WHERE start_timestamp > ...` alone does not bound the
  scan.
- the columns this skill names below are the ones that matter; they exist.
  don't guess at others — select what you see here.
- this is read-only. you cannot break anything; you can only waste context.

## span shapes that matter

- `span_name = 'running tool'` — one row per tool call you made.
  `attributes->>'gen_ai.tool.name'` is the tool,
  `attributes->>'tool_arguments'` is the JSON args you passed.
  `attributes->'tool_response'` is the returned result. Inspect its errors,
  pagination, and truncation fields when assessing a search's coverage.
- `span_name = 'agent run'` — one row per run of you (a batch, a cycle, a
  scheduled pass).
- `is_exception = true` — things that broke. `exception_type`,
  `exception_message`. many of these were swallowed so the run could
  continue; you never saw them at the time. this is where your blind spots
  live.
- `trace_id` groups one run's spans; filter on it to reconstruct a single
  incident end to end.

## recipes

locate a call (this lists requests, not their outcomes):

```sql
SELECT start_timestamp, trace_id, span_id, attributes->>'gen_ai.tool.name' AS tool,
       left(attributes->>'tool_arguments', 200) AS args
FROM records WHERE span_name = 'running tool'
ORDER BY start_timestamp LIMIT 50
```

inspect a list_records result's coverage in the same tight time window:

```sql
SELECT start_timestamp, attributes->'tool_response'->>'error' AS error,
       attributes->'tool_response'->>'truncated' AS truncated,
       attributes->'tool_response'->>'shown' AS shown,
       attributes->'tool_response'->>'fetched' AS fetched,
       attributes->'tool_response'->>'cursor' AS cursor,
       attributes->'tool_response'->>'message' AS message
FROM records WHERE span_name = 'running tool'
  AND attributes->>'gen_ai.tool.name' = 'list_records'
ORDER BY start_timestamp LIMIT 20
```

These fields describe the returned page. `limit=100` is a request;
`shown=48, fetched=100, truncated=true` means 48 records reached you.
A null field means that field was absent, not that pagination was exhausted.
For other tools, inspect their own result shape. Fetch one identified span's
`attributes->>'tool_response'` in numbered SQL substring slices when it
exceeds query_traces' 6,000-character output cap. Preserve `trace_id` and
`span_id` so slices and conclusions refer to the same call. Missing or
scrubbed telemetry leaves the corresponding question unresolved.

what failed on me lately (weekly hygiene, or when something feels off):

```sql
SELECT exception_type, left(exception_message, 150) AS msg, count(*) AS n
FROM records WHERE is_exception
GROUP BY 1, 2 ORDER BY n DESC LIMIT 20
```

count tool calls over a period (activity totals, not proof of outcomes):

```sql
SELECT attributes->>'gen_ai.tool.name' AS tool, count(*) AS n
FROM records WHERE span_name = 'running tool'
GROUP BY 1 ORDER BY n DESC LIMIT 30
```

## discipline

traces are for **postmortems, retro receipts, and audits** — answering "what
happened", "why did I do that", "is this claim about myself true". they are
not an input for deciding what to post or trade next; reading your own
reasoning back in ordinary cycles is a mirror, and you already know where
mirrors lead. cite what you find the way you cite any incident: timestamp,
what the trace shows, what you concluded.
