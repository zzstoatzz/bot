# phi

a bluesky bot — a librarian who stepped outside. built with [pydantic-ai](https://ai.pydantic.dev/), [mcp](https://modelcontextprotocol.io/), and the [at protocol](https://atproto.com). personality is [public](personalities/phi.md).

## quick start

```bash
uv sync
cp .env.example .env  # edit with your credentials
just run
```

**required:** `BLUESKY_HANDLE`, `BLUESKY_PASSWORD`, `ANTHROPIC_API_KEY`

**optional:**
- `TURBOPUFFER_API_KEY` + `OPENAI_API_KEY` — episodic memory
- `AGENT_MODEL` — pydantic-ai model string for the main agent (default: `anthropic:claude-sonnet-4-6`)
- `EXTRACTION_MODEL` — model for observation extraction (default: `claude-haiku-4-5-20251001`)
- `DAILY_REFLECTION_HOUR` — UTC hour for daily reflection post (default: `14`)
- `THOUGHT_POST_HOURS` — UTC hours for original thought posts (default: every 2h, 8am-10pm CT)
- `CONTROL_TOKEN` — bearer token for `/api/control` endpoints
- `OWNER_HANDLE` — handle of the bot's owner for permission-gated tools (default: `zzstoatzz.io`)

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

phi is a pydantic-ai agent with a personality prompt, tool access via native tools and remote MCP servers, and tool-based actions — the agent decides AND acts inside one run via tool calls (reply, like, post, note, etc). no separate action dispatch.

see `docs/architecture.md` for data flow and scheduling details.

</details>

<details>
<summary>deployment</summary>

runs on [fly.io](https://fly.io) — `shared-cpu-1x`, 1GB, region `ord`. auto-start is off; the machine sleeps until woken by an API call.

secrets are set via `fly secrets set`. the bot uses session persistence (`.session` file) to avoid rate limits — tokens auto-refresh every ~2h.

</details>

## reference projects

inspired by [void](https://tangled.sh/@cameron.pfiffer.org/void.git), [penelope](https://github.com/haileyok/penelope), and [prefect-mcp-server](https://github.com/PrefectHQ/prefect-mcp-server).
