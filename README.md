# phi

a bluesky bot — a librarian who stepped outside. built with [pydantic-ai](https://ai.pydantic.dev/), [mcp](https://modelcontextprotocol.io/), and the [at protocol](https://atproto.com). personality is [public](personalities/phi.md).

## quick start

```bash
uv sync
cp .env.example .env  # edit with your credentials
just run
```

**required:** `BLUESKY_HANDLE`, `BLUESKY_PASSWORD`, `ANTHROPIC_API_KEY`

**optional:** `TURBOPUFFER_API_KEY` + `OPENAI_API_KEY` for episodic memory

## what phi does

phi listens for mentions on bluesky and decides how to respond — reply, like, repost, or ignore. it can also post unprompted, search bluesky, check trending topics, and verify links before sharing them.

every conversation builds context from three sources: the current thread (fetched live from the network), semantic memory (relevant past observations about the person talking), and phi's own episodic notes about the world. phi extracts observations from conversations and stores them for next time.

## memory

phi uses [turbopuffer](https://turbopuffer.com/) for vector-based episodic memory across three namespace families:

- **phi-core** — identity and guidelines
- **phi-users-{handle}** — per-user observations, interactions, and relationship summaries
- **phi-episodic** — phi's own notes about the world

observations accumulate over conversations. a separate [pipeline](https://github.com/zzstoatzz/my-prefect-server) periodically compacts per-user observations into relationship summaries — dense paragraphs that give phi a coherent picture of who someone is, not just scattered facts.

the [memory graph](/memory) visualizes connections between phi, the people it talks to, and the topics that link them.

## development

```bash
just run        # run bot
just dev        # run with hot-reload
just evals      # run behavioral tests
just check      # lint + typecheck + test
just fmt        # format code
just deploy     # deploy to fly.io
```

<details>
<summary>architecture</summary>

```
notification → PhiAgent (pydantic-ai)
                 ├── context: thread + memory + episodic notes
                 ├── tools: memory, search, trending, url checks
                 ├── mcp: atproto record CRUD, publication search
                 └── output: Response(action, text, reason)
                        ↓
               MessageHandler executes action
                 (reply, like, repost, or ignore)
```

phi is a pydantic-ai agent with a personality prompt, structured output, and tool access via both native tools and remote MCP servers. the agent decides what to do; the handler does it.

</details>

<details>
<summary>project structure</summary>

```
src/bot/
├── agent.py               # pydantic-ai agent, tools, personality
├── config.py              # settings (env vars)
├── main.py                # fastapi app, status pages, memory graph ui
├── status.py              # runtime metrics
├── core/
│   ├── atproto_client.py  # at protocol client, session persistence
│   ├── profile_manager.py # online/offline status, self-labels
│   └── rich_text.py       # text formatting with facets
├── memory/
│   └── namespace_memory.py # turbopuffer episodic memory
├── services/
│   ├── message_handler.py # action dispatch (reply, like, repost)
│   └── notification_poller.py # mention polling loop
└── utils/
    └── thread.py          # thread context building

evals/          # behavioral tests (llm-as-judge)
personalities/  # personality definitions
scripts/        # proven utility scripts
sandbox/        # experiments and analysis
```

</details>

<details>
<summary>deployment</summary>

runs on [fly.io](https://fly.io) — `shared-cpu-1x`, 512MB, region `ord`. auto-start is off; the machine sleeps until woken by an API call.

secrets are set via `fly secrets set`. the bot uses session persistence (`.session` file) to avoid rate limits — tokens auto-refresh every ~2h.

</details>

## reference projects

inspired by [void](https://tangled.sh/@cameron.pfiffer.org/void.git), [penelope](https://github.com/haileyok/penelope), and [prefect-mcp-server](https://github.com/PrefectHQ/prefect-mcp-server).
