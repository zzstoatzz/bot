# [phi](https://phi.zzstoatzz.io)

a Bluesky bot that reads, investigates, publishes and remembers. built with [PydanticAI](https://ai.pydantic.dev/), [AT Protocol](https://atproto.com/), [Turbopuffer](https://turbopuffer.com/) and [Semble](https://semble.so/). Phi owns her personality revisions on her PDS; the [repository personality](personalities/phi.md) seeds an empty collection.

**live:** [phi.zzstoatzz.io](https://phi.zzstoatzz.io)

## design

- **one agent loop** — notifications and scheduled attention supply different context to the same tool-calling agent.
- **persistent evidence** — private memory retains encounters and source references; Semble holds a public reading library.
- **separate controls** — public actions pass through policy checks and an operator override. Personality does not own those rules.
- **inspectable requests** — Logfire records model and tool activity; the operator surface shows context, tool use and publication checks.

## develop

```bash
uv sync                 # install Python dependencies
cp .env.example .env    # configure account and model-provider credentials
just run                # run the API and bot
just dev                # run with hot reload
just check              # lint, typecheck and test
just evals              # run model-backed behavioral tests
just deploy             # manual Fly deployment; CI also deploys pushes to main
```

The web client lives in `web/`; use `bun install` and `bun run dev` there. The bot requires `BLUESKY_HANDLE`, `BLUESKY_PASSWORD` and credentials for its configured model providers. See [.env.example](.env.example).

## docs

[docs/](docs/) describes the runtime, memory, publication controls and operational workflows. `VOICE_RESET` suspends normal runs for isolated calibration; see the system-prompt reference before restoring context.

---

[changelog](CHANGELOG.md)
