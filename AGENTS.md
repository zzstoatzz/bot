phi — a bluesky bot with episodic memory. python + pydantic-ai + fastapi + turbopuffer.

## development

- `just run` / `just dev` (hot-reload) / `just deploy` (fly.io)
- `just evals` — behavioral tests (llm-as-judge)
- `just check` — lint + typecheck + test
- `just loq-relax <file>` — when a file exceeds its line limit, relax it. never manually edit loq.toml or compress code to fit
- work from repo root

## python style

- 3.10+ typing (`T | None`, `list[T]`)
- prefer functional over OOP
- imports at the top — no deferred imports unless circular
- never use `pytest.mark.asyncio`

## deployment

fly.io app `zzstoatzz-phi`. deploys triggered by `v*` tags via tangled CI. `just release <version>` tags and pushes. `just deploy` for manual.

## key architecture

- all notification types run through the full agent loop — phi decides what's worth responding to
- actions (reply, like, post) happen via tool calls inside the agent run, not structured output
- personality is separate from operational instructions
- memory: turbopuffer namespaces (`phi-users-{handle}`, `phi-episodic`)
- exploration is event-driven: curiosity queue on PDS, drained when idle
- MCP servers: pdsx (atproto record CRUD), pub-search (publication search)
