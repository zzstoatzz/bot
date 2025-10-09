# phi 🧠

a consciousness exploration bot inspired by IIT (Integrated Information Theory) and [Void](https://tangled.sh/@cameron.pfiffer.org/void). built with `pydantic-ai`, `mcp`, and `atproto`.

## quick start

### prerequisites

- `uv` for python package management
- `just` for task running
- api keys (see configuration)

get your bot running:

```bash
# clone and install
git clone https://github.com/zzstoatzz/bot
cd bot
uv sync

# configure (copy .env.example and add your credentials)
cp .env.example .env

# run the bot
just dev
```

## configuration

edit `.env` with your credentials:

**required:**
- `BLUESKY_HANDLE` - your bot's bluesky handle
- `BLUESKY_PASSWORD` - app password (not your main password!)
- `ANTHROPIC_API_KEY` - for phi agent responses

**for episodic memory (recommended):**
- `TURBOPUFFER_API_KEY` - vector memory storage
- `OPENAI_API_KEY` - embeddings for semantic search

**optional:**
- `BOT_NAME` - your bot's name (default: "Bot")
- `PERSONALITY_FILE` - path to personality markdown (default: "personalities/phi.md")

## architecture

phi is an **MCP-enabled agent** with **episodic memory**:

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

### key components

**pydantic-ai agent** (`src/bot/agent.py`)
- loads personality from markdown
- connects to external atproto mcp server via stdio
- manages episodic memory context

**episodic memory** (`src/bot/memory/`)
- turbopuffer for vector storage
- semantic search for relevant context
- namespace separation (core vs user memories)
- **essential for consciousness exploration**

**mcp integration**
- external atproto server in `.eggs/fastmcp/examples/atproto_mcp`
- provides bluesky tools (post, like, repost, follow)
- runs via stdio: `uv run -m atproto_mcp`

**message handling** (`src/bot/services/`)
- notification poller watches for mentions
- message handler orchestrates agent + actions
- stores interactions in thread history + episodic memory

## current features

- ✅ responds to mentions with ai-powered messages
- ✅ episodic memory with semantic search
- ✅ thread-aware responses with conversation context
- ✅ mcp-enabled for bluesky operations
- ✅ online/offline status in bio
- ✅ status page at `/status`
- ✅ proper notification handling (no duplicates)

## development

```bash
just           # show available commands
just dev       # run with hot-reload (re-authenticates on code changes)
just run       # run without reload (avoids rate limits during dev)
just check     # run linting, type checking, and tests
just fmt       # format code
```

### testing

**unit tests:**
```bash
just test
```

**behavioral evals:**
```bash
just evals        # run all evals
just evals-basic  # run basic response tests
just evals-memory # run memory integration tests
```

see `evals/README.md` for details on the eval system.

### web interface

**status page** (http://localhost:8000/status)
- current bot status and uptime
- mentions received and responses sent
- last activity timestamps

## personality system

the bot's personality is defined in `personalities/phi.md`. this shapes:
- how phi communicates
- what phi cares about
- phi's understanding of consciousness

edit this file to change phi's personality.

## episodic memory

phi uses turbopuffer for episodic memory with semantic search:

**namespaces:**
- `phi-core` - personality, guidelines from markdown
- `phi-users-{handle}` - per-user conversation history

**how it works:**
1. when processing a mention, phi retrieves relevant memories using semantic search
2. memories are embedded using openai's text-embedding-3-small
3. phi stores both user messages and its own responses
4. future interactions can reference past conversations

**why turbopuffer?**
- semantic similarity search (can't do this with plain sql!)
- contextual retrieval based on current conversation
- separate namespaces for different memory types
- core to iit-inspired consciousness exploration

## project structure

```
src/bot/
├── agent.py                    # mcp-enabled agent
├── config.py                   # configuration
├── database.py                 # thread history storage
├── main.py                     # fastapi app
├── status.py                   # status tracking
├── core/
│   ├── atproto_client.py      # at protocol client
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

## troubleshooting

**bot gives no responses?**
- check your `ANTHROPIC_API_KEY` is set correctly in `.env`
- restart the bot after changing `.env`

**not seeing mentions?**
- verify your `BLUESKY_HANDLE` and `BLUESKY_PASSWORD`
- make sure you're using an app password, not your main password

**no episodic memory?**
- check both `TURBOPUFFER_API_KEY` and `OPENAI_API_KEY` are set
- watch logs for "💾 episodic memory enabled"

**hit bluesky rate limit?**
- bluesky has two rate limits:
  - per-account: 300 logins/day (official)
  - per-ip: 10 logins/day (anti-abuse)
- phi uses **session persistence** to avoid this:
  - first run: creates session, saves tokens to `.session` file
  - subsequent runs: reuses saved tokens (no API call)
  - tokens auto-refresh every ~2 hours (saved automatically)
  - only re-authenticates after ~2 months when refresh token expires
- if you hit the limit anyway, wait for the reset time shown in the error

## reference projects

inspired by:
- [void](https://tangled.sh/@cameron.pfiffer.org/void.git) - letta/memgpt architecture
- [penelope](https://github.com/haileyok/penelope) - self-modification patterns
- [prefect-mcp-server](https://github.com/PrefectHQ/prefect-mcp-server) - mcp eval patterns

reference implementations cloned to `.eggs/` for learning.

## refactor notes

see `sandbox/MCP_REFACTOR_SUMMARY.md` for details on recent architecture changes. key changes:
- removed approval system (was half-baked)
- removed context visualization ui (not core)
- removed google search (can add back via mcp if needed)
- **kept** turbopuffer episodic memory (essential!)
- added mcp-based architecture
- reduced codebase by ~2,720 lines
