# observability

phi is instrumented with [logfire](https://logfire.pydantic.dev), which owns the
console and exports OTel spans. Everything below is a property of the
integration that cost time to discover once.

## setup

- The dependency is `logfire[fastapi]`. There is no `pydantic-ai` extra —
  logfire auto-instruments pydantic-ai whenever both are installed.
- Use `uv tree`, not `uv pip show`, to inspect what is actually resolved.

## logfire owns the console

logfire ships its own rich-based console span exporter. When it is exporting,
a stdlib `StreamHandler` writes a second, competing stream to the same
terminal — remove it and bridge stdlib logs into the OTel pipeline with
`LogfireLoggingHandler` instead, so there is one ordered output.

`ConsoleOptions(verbose=True)` dumps file paths, logger names, and arguments on
every line. It is almost never what you want.

## uvicorn fights for the handlers

uvicorn installs its own logging handlers *on startup* — after module-level code
has already run, so configuring logging at import time is not enough. They are
cleared in the lifespan via `_clear_uvicorn_handlers()`. If log output suddenly
doubles or loses formatting, this is the first thing to check.

## noise

httpx logs every request at INFO, which duplicates logfire's own HTTP span
instrumentation. It is silenced at WARNING.

## querying

Traces are queryable via the logfire MCP (`query_run`). Two habits worth
keeping: `query_schema_reference` before writing non-trivial SQL, and never
truncating a `tool_response` with `left(...)` when the question is whether a
value was present — truncating your own evidence and then reporting uncertainty
is worse than not looking.

## Tool exposure and invocation journal

`/api/tool-usage` and the operator page show a rolling 30-day window from
`/data/tool_usage.sqlite3`. `core/tool_usage.py` uses the installed PydanticAI
capability hooks: `before_model_request` observes final function definitions;
`wrap_tool_execute` observes invocation and return/raise without changing either.
Request/run counts describe exposure, not attention. The journal persists restarts
and stores no tool arguments, results, private notes or error messages.

Native tools with zero exposure are explicitly unobserved. Remote tools appear
once discovered in a request or invoked. MCP code-mode's nested operations are
inside one tool call and require inspecting its Logfire span. Skill loading is
counted as `load_skill`, not as using every capability described by that skill.
A returned result may be a refusal or text error; unfinished means no completion
was recorded, which can include an interrupted process. It is not a tool-success
metric. Observation failures log errors and do not alter Phi's execution.

The journal starts at deployment; older use is unknown there. Historical Logfire
queries can investigate earlier activity, but cannot establish exposure from
invocation counts alone. No tool-use quota or automatic retirement is implied.


## Prompt caching: September 11 verification

A private probe on the deployed Phi machine used captured production instructions
and a read-only tool with the installed provider settings. Both Sonnet 5 and Luna
completed two runs and invoked the tool. The second run reported 34,422 cache-read
tokens of 34,870 input tokens on Sonnet, and 23,278 of 23,476 on Luna. These are
usage totals across each tool loop, not unique prefix lengths. This verifies the
transport/settings boundary, not a complete public-action run or voice evaluation.

For September 10 18:00Z through September 11 18:00Z, Logfire recorded 173 main
Phi requests: 14,100,879 input tokens, 13,097,244 cache reads (92.9%), and
1,003,289 cache writes. The helper roles added 172,972 input tokens across 82
requests; their inspected spans did not expose cache reads. Missing metrics are
not evidence of zero cache use. No causal latency savings were established.

The old `/api/cache` recorder shared mutable run state across concurrent tasks.
Its per-run trace attribution and collapse counts were unreliable: a chicken
run included response counts absent from that trace. The corrected recorder
uses task-local state and starts a fresh versioned window. Historical snapshots
must not be used to attribute a prompt regression. The conservative input-cost
estimate prices all Anthropic writes at the longer TTL; it is not total invoice
savings. Cross-provider totals have no cost estimate without model-specific rates.

### Alert observations and workload recovery

`ALERT WATCH` groups observations by alert ID. Its age and count describe that
notification history, not the duration or number of failures of one flow. The
block carries the latest observation and alert evaluation time separately from
the last matching detail. A quiet, missing, or disabled alert does not prove
workload recovery. Check subsequent runs of the affected workload before
reporting that an old failure is continuing or has recovered.
