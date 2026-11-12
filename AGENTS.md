# phi

Python bot with a FastAPI web surface. Work from the repository root.

## development

- `just run` starts the app; `just dev` enables hot reload.
- `just check` runs lint, typechecking and tests; `just evals` runs behavioral evaluations.
- Use `just loq-relax <file>` for justified line-limit changes; do not edit
  `loq.toml` manually or compress code to satisfy it.
- Imports belong at the top except for circular dependencies. Tests do not use
  `pytest.mark.asyncio`. Tool parameters use `Annotated[T, Field(description=...)]`.

## behavior and authority

Read [safety boundaries](docs/safety.md) before changing tools, permissions or
public delivery, and [context ownership](docs/memory.md) before changing prompts
or memory. Signals are evidence for Phi to judge; actions happen through tools.
Keep personality separate from operational rules and per-tool guidance.
Before changing scheduling, entry points or seemingly accidental behavior, read
[design lessons](docs/patterns.md) and [entry-point contracts](docs/architecture.md#entry-points).
A broken action needs its boundary repaired without silently removing its trigger.

Operator automation must never post, like, repost or approve work as Nate's main
account (`did:plc:xbtmt2zjwlrfegqvch7fboei`). Devlog communication uses only
`did:plc:o53crari67ge7bvbv273lxln`; verify the actual client's `whoami` before
writing. Credentials from another project grant no authority. Do not manufacture
operator approval to complete a test. Preserve the independent policy judge,
MCP mutation guard and operator override.

Changes to `operator-guidance.md` require operator approval before deployment;
its review date does not automatically remove its contents.

## skills and integration

`skills/` belongs to Phi at runtime; `.agents/skills/` is for contributors and
operators. Put new capabilities in the appropriate namespace. When editing vendored
runtime skills, preserve their upstream attribution and license files. Preserve the
`.claude/skills` compatibility link. Use the PDSX MCP for AT Protocol writes.

For MCP or skill integration, read [MCP contracts](docs/mcp.md). A tool named by
prompts or skills must survive tool filtering and be available in that run.
For prompt changes, update `docs/system-prompt.md`; `tests/test_docs_sync.py`
checks prompt functions and policy slugs. Use [architecture](docs/architecture.md)
and [the docs index](docs/README.md) for the relevant subsystem.

## deployment

CI deploys every push to main through `.tangled/workflows/deploy.yml`.
`just deploy` is the fallback when CI is unavailable. Push both Tangled `origin`
and the `github` mirror, which Phi's changelog tool reads. Keep self-source
references aligned if the repository moves. Read [runtime health](docs/runtime-health.md)
when changing startup, polling or restart behavior. Keep secrets out of terminal
output and Git. Record shipped rationale in `CHANGELOG.md`; keep current design in docs.
