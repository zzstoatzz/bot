# phi

a bluesky bot inspired by [integrated information theory](https://en.wikipedia.org/wiki/Integrated_information_theory). built with `pydantic-ai`, `mcp`, and the [at protocol](https://atproto.com).

## quick start

```bash
# clone and install
git clone https://github.com/zzstoatzz/bot
cd bot
uv sync

# configure
cp .env.example .env
# edit .env with your credentials

# run
just run
```

**required env vars:**
- `BLUESKY_HANDLE` / `BLUESKY_PASSWORD` - bot account (use app password)
- `ANTHROPIC_API_KEY` - for agent responses

**optional (for episodic memory):**
- `TURBOPUFFER_API_KEY` + `OPENAI_API_KEY` - semantic memory

## features

- ✅ responds to mentions with ai-powered messages
- ✅ episodic memory with semantic search (turbopuffer)
- ✅ thread-aware conversations
- ✅ mcp-enabled (atproto tools via stdio)
- ✅ session persistence (no rate limit issues)
- ✅ behavioral test suite with llm-as-judge

## development

```bash
just run        # run bot
just dev        # run with hot-reload
just evals      # run behavioral tests
just check      # lint + typecheck + test
just fmt        # format code
```

<details>
<summary>architecture</summary>

phi is an **mcp-enabled agent** with **episodic memory**:

```
┌─────────────────────────────────────┐
│     Notification Arrives            │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│     PhiAgent (PydanticAI)           │
│  ┌───────────────────────────────┐  │
│  │ System Prompt: personality.md │  │
│  └───────────────────────────────┘  │
│              ↓                      │
│  ┌───────────────────────────────┐  │
│  │ Context Building:             │  │
│  │ • Thread history (SQLite)     │  │
│  │ • Episodic memory (TurboPuffer)│ │
│  │   - Semantic search           │  │
│  │   - User-specific memories    │  │
│  └───────────────────────────────┘  │
│              ↓                      │
│  ┌───────────────────────────────┐  │
│  │ Tools (MCP):                  │  │
│  │ • post() - create posts       │  │
│  │ • like() - like content       │  │
│  │ • repost() - share content    │  │
│  │ • follow() - follow users     │  │
│  └───────────────────────────────┘  │
│              ↓                      │
│  ┌───────────────────────────────┐  │
│  │ Structured Output:            │  │
│  │ Response(action, text, reason)│  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
               ↓
┌─────────────────────────────────────┐
│     MessageHandler                  │
│     Executes action                 │
└─────────────────────────────────────┘
```

**key components:**

- **pydantic-ai agent** - loads personality, connects to mcp server, manages memory
- **episodic memory** - turbopuffer for vector storage with semantic search
- **mcp integration** - external atproto server provides bluesky tools via stdio
- **session persistence** - tokens saved to `.session`, auto-refresh every ~2h

</details>

<details>
<summary>episodic memory</summary>

phi uses turbopuffer for episodic memory with semantic search.

**namespaces:**
- `phi-core` - personality, guidelines
- `phi-users-{handle}` - per-user conversation history

**how it works:**
1. retrieves relevant memories using semantic search
2. embeds using openai's text-embedding-3-small
3. stores user messages and bot responses
4. references past conversations in future interactions

**why vector storage?**
- semantic similarity (can't do this with sql)
- contextual retrieval based on current conversation
- enables more natural, context-aware interactions

</details>

<details>
<summary>project structure</summary>

```
src/bot/
├── agent.py                    # mcp-enabled agent
├── config.py                   # configuration
├── database.py                 # thread history storage
├── main.py                     # fastapi app
├── core/
│   ├── atproto_client.py      # at protocol client (session persistence)
│   ├── profile_manager.py     # online/offline status
│   └── rich_text.py           # text formatting
├── memory/
│   └── namespace_memory.py    # turbopuffer episodic memory
└── services/
    ├── message_handler.py     # agent orchestration
    └── notification_poller.py # mention polling

evals/                         # behavioral tests
personalities/                 # personality definitions
sandbox/                       # docs and analysis
```

</details>

<details>
<summary>troubleshooting</summary>

**bot gives no responses?**
- check `ANTHROPIC_API_KEY` in `.env`
- restart after changing `.env`

**not seeing mentions?**
- verify `BLUESKY_HANDLE` and `BLUESKY_PASSWORD`
- use app password, not main password

**no episodic memory?**
- check both `TURBOPUFFER_API_KEY` and `OPENAI_API_KEY` are set
- watch logs for "💾 episodic memory enabled"

**hit bluesky rate limit?**
- phi uses session persistence to avoid this
- first run: creates `.session` file with tokens
- subsequent runs: reuses tokens (no api call)
- tokens auto-refresh every ~2h
- only re-authenticates after ~2 months
- rate limits (10/day per ip, 300/day per account) shouldn't be an issue

</details>

<details>
<summary>refactor notes</summary>

see `sandbox/MCP_REFACTOR_SUMMARY.md` for details.

**what changed:**
- removed approval system (half-baked)
- removed context viz ui (not core)
- removed google search (can add back via mcp)
- **kept turbopuffer** (essential for episodic memory)
- added mcp-based architecture
- added session persistence
- reduced codebase by ~2,720 lines

</details>

## reference projects

inspired by [void](https://tangled.sh/@cameron.pfiffer.org/void.git), [penelope](https://github.com/haileyok/penelope), and [prefect-mcp-server](https://github.com/PrefectHQ/prefect-mcp-server).
