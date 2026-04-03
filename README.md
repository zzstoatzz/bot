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

phi listens for all notification types on bluesky — mentions, replies, quotes, likes, reposts, follows — and decides how to respond. it can search live posts, check trending topics, query the [cosmik](https://cosmik.network)/[semble](https://semble.so) network for public knowledge, create public records (notes, bookmarks, connections), and post unprompted via daily reflections.

every conversation builds context from: the current thread (fetched live from ATProto), private memory (past observations about the person talking), and public network knowledge (cards and links indexed by semble). phi extracts observations from conversations and stores them for next time.

## memory

phi has two memory systems with different visibility:

- **private** — [turbopuffer](https://turbopuffer.com/) vector memory for per-user observations, interactions, and relationship summaries. this is what phi uses to remember people across conversations.
- **public** — [cosmik](https://cosmik.network) records on phi's PDS (notes, bookmarks, connections), indexed by [semble](https://semble.so) for semantic search. anything phi finds worth preserving publicly becomes a card on the network.

notes and bookmarks are dual-written: private for fast recall, public for network discovery.

a separate [pipeline](https://github.com/zzstoatzz/my-prefect-server) enriches memory offline:
- **compact** (hourly): synthesizes per-user relationship summaries, extracts observations from nate's liked posts
- **morning** (daily): deduplicates tags, discovers relationships between topics, promotes observations to semble as public cosmik cards

the [memory graph](/memory) visualizes connections between phi, the people it talks to, and the topics that link them.

## mention consent

phi only sends notifications (via AT Protocol mention facets) to people who are part of the current conversation — the person who messaged phi, plus nate's accounts. third-party @handles in phi's replies render as plain text, visible but silent. this is enforced at two layers: code (`parse_mentions()` gates facets behind an `allowed_handles` set) and prompt (operational instructions tell phi not to @mention third parties).

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
                 ├── context: thread (ATProto) + private memory (tpuf) + network (semble)
                 ├── native tools: memory, search, cosmik records, etc (see agent.py)
                 ├── mcp servers: pdsx (atproto CRUD), pub-search (publications)
                 └── output: Response(action, text, reason)
                        ↓
               MessageHandler executes action
```

phi is a pydantic-ai agent with a personality prompt, structured output, and tool access via both native tools and remote MCP servers. the agent decides what to do; the handler does it. tools are defined in `agent.py`.

</details>

<details>
<summary>project structure</summary>

```
src/bot/
├── agent.py               # pydantic-ai agent, tools, personality
├── types.py               # cosmik record models (cards, connections)
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
