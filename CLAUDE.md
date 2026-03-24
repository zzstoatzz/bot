phi — a bluesky bot with episodic memory. python + pydantic-ai + fastapi + turbopuffer.

## development

- `just run` / `just dev` (hot-reload) / `just deploy` (fly.io)
- `just evals` — behavioral tests (llm-as-judge)
- `just check` — lint + typecheck + test
- work from repo root

## python style

- 3.10+ typing (`T | None`, `list[T]`)
- prefer functional over OOP
- imports at the top — no deferred imports unless circular
- never use `pytest.mark.asyncio`

## project structure

```
src/bot/
├── agent.py               # pydantic-ai agent, tools, personality
├── config.py              # settings (env vars)
├── main.py                # fastapi app, status pages, memory graph
├── status.py              # runtime metrics
├── core/                  # atproto client, profile management
├── memory/                # turbopuffer episodic memory
├── services/              # notification polling, message handling
└── utils/                 # thread context, text formatting

personalities/             # personality definitions (public)
evals/                     # behavioral tests
scripts/                   # proven utility scripts
sandbox/                   # experiments (graduate to scripts/ once proven)
.eggs/                     # cloned reference projects
```

## deployment

fly.io app `zzstoatzz-phi`. every push to main triggers `.tangled/workflows/deploy.yml` — this means even doc-only changes cause a deploy. consider switching to tag-based triggers (like zat uses `tag: "v*"`) or adding a separate CI workflow for tests.

## key architecture

- all notification types (mentions, replies, quotes, likes, reposts, follows) run through the full agent loop — phi decides what's worth responding to
- personality is separate from operational instructions (agent.py `OPERATIONAL_INSTRUCTIONS`)
- memory: turbopuffer namespaces (`phi-core`, `phi-users-{handle}`, `phi-episodic`)
- relationship summaries are compacted by a separate pipeline in my-prefect-server
- MCP servers: pdsx (atproto record CRUD), pub-search (publication search)
