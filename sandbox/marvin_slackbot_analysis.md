# Marvin Slackbot Architecture Analysis

## Overview

The Marvin slackbot is a sophisticated AI-powered Slack integration built with FastAPI and leveraging advanced patterns for conversation management, tool usage, and memory persistence. The architecture demonstrates several patterns that would be valuable for a Bluesky bot implementation.

## Core Architecture Patterns

### 1. FastAPI Integration with Async Event Handling

The bot uses FastAPI with an async lifespan pattern for resource management:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with Database.connect(settings.db_file) as db:
        app.state.db = db
        yield

app = FastAPI(lifespan=lifespan)
```

Key benefits:
- Clean resource lifecycle management
- Database connection shared across requests via `app.state`
- Non-blocking async handling of Slack events
- Fire-and-forget pattern with `asyncio.create_task()` for immediate response to Slack

### 2. Agent Architecture with pydantic-ai

The bot uses `pydantic-ai` for structured agent creation with several sophisticated patterns:

#### Multi-Tier Agent System
- **Main Agent**: Handles user interactions and delegates to specialized tools
- **Research Agent**: Specialized sub-agent for thorough documentation research
- Both agents use structured result types (`ResearchFindings`) for predictable outputs

#### Context Injection Pattern
```python
Agent[UserContext, str](
    deps_type=UserContext,
    tools=[...],
)
```
- Clean dependency injection of user context to all tools
- Context includes user ID, notes, thread info, workspace details

#### Dynamic System Prompts
```python
@agent.system_prompt
def personality_and_maybe_notes(ctx: RunContext[UserContext]) -> str:
    return DEFAULT_SYSTEM_PROMPT + (
        f"\n\nUser notes: {ctx.deps['user_notes']}"
        if ctx.deps["user_notes"] else ""
    )
```

### 3. Memory and Vector Store Integration

The bot implements a sophisticated memory system using TurboPuffer vector store:

#### User-Specific Namespacing
```python
namespace=f"{settings.user_facts_namespace_prefix}{user_id}"
```
- Each user has their own vector namespace for facts
- Facts are retrieved based on query relevance
- Clean separation of user data

#### Fact Storage Pattern
```python
@agent.tool
async def store_facts_about_user(
    ctx: RunContext[UserContext], facts: list[str]
) -> str:
    with TurboPuffer(namespace=f"...{ctx.deps['user_id']}") as tpuf:
        tpuf.upsert(documents=[Document(text=fact) for fact in facts])
```

### 4. Conversation Thread Management

The bot maintains conversation history using SQLite with async wrappers:

#### Thread-Based Storage
- Messages stored per thread using `thread_ts` as key
- Full conversation history preserved as `ModelMessage` objects
- Efficient serialization with `ModelMessagesTypeAdapter`

#### Automatic Summarization
```python
@handle_message.on_completion
async def summarize_thread_so_far(flow: Flow, flow_run: FlowRun, state: State[Any]):
    if len(conversation) % 4 != 0:  # every 4 messages
        return
    await summarize_thread(result["user_context"], conversation)
```

### 5. Tool Usage Patterns

#### Tool Decoration and Monitoring
The `WatchToolCalls` context manager provides:
- Real-time progress updates during tool execution
- Tool usage counting and statistics
- Clean separation of tool execution from business logic

#### Prefect Integration
```python
@task(name="run agent loop", cache_policy=NONE)
async def run_agent(...) -> AgentRunResult[str]:
    with WatchToolCalls(settings=decorator_settings):
        result = await create_agent().run(...)
```

### 6. Asset Tracking and Data Lineage

The bot implements Prefect asset tracking for data lineage:

```python
@materialize(user_facts, asset_deps=[slack_thread, slackbot])
async def materialize_user_facts():
    add_asset_metadata(user_facts, {...})
```

Key patterns:
- Assets represent different data products (threads, summaries, user facts)
- Clear dependency tracking between assets
- Rich metadata for observability

## Key Utilities and Patterns to Adopt

### 1. Progress Messaging
Real-time feedback during long-running operations:
```python
progress = await create_progress_message(
    channel_id=channel_id, 
    thread_ts=thread_ts, 
    initial_text="🔄 Thinking..."
)
```

### 2. Token Management
Intelligent message truncation and length validation:
```python
if msg_len > USER_MESSAGE_MAX_TOKENS:
    slice_tokens(cleaned_message, USER_MESSAGE_MAX_TOKENS)
```

### 3. Error Handling with Notifications
```python
slack_webhook = await SlackWebhook.load("marvin-bot-pager")
await slack_webhook.notify(body=f"Error: {e}", subject="Bot Error")
```

### 4. Configuration Management
- Settings via pydantic-settings with prefixes
- Mix of environment variables and Prefect Variables
- Secret management through Prefect Blocks

### 5. Research Pattern
The research agent pattern is particularly powerful:
- Multiple search strategies with different tools
- Confidence levels in responses
- Knowledge gap acknowledgment
- Structured findings with links

## Recommendations for Bluesky Bot

1. **Adopt the Multi-Agent Architecture**: Use a main agent with specialized sub-agents for different tasks (posting, research, conversation)

2. **Implement Vector-Based Memory**: Use TurboPuffer with user-specific namespaces for personalization

3. **Use Structured Contexts**: Define clear context types (e.g., `PostContext`, `ConversationContext`) for dependency injection

4. **Async Event Handling**: Use FastAPI with async patterns for handling Bluesky firehose events

5. **Progress Feedback**: Implement progress indicators for long-running operations (useful for thread replies)

6. **Tool Monitoring**: Implement the `WatchToolCalls` pattern for observability

7. **Asset Tracking**: Track posts, threads, and user interactions as Prefect assets for data lineage

8. **Conversation Management**: Store conversation history with efficient serialization

9. **Error Recovery**: Implement webhook-based error notifications and automatic retries

10. **Dynamic Prompting**: Use context-aware system prompts that incorporate user history

## Architecture Diagram

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   FastAPI App   │────▶│  Event Handler   │────▶│   Agent Loop    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │                         │
         │                       │                         ▼
         ▼                       ▼                 ┌───────────────┐
┌─────────────────┐     ┌──────────────────┐     │ Research Agent│
│   SQLite DB     │     │  User Context    │     └───────────────┘
└─────────────────┘     └──────────────────┘              │
         │                       │                         ▼
         │                       ▼                 ┌───────────────┐
         │              ┌──────────────────┐      │     Tools     │
         │              │  Vector Store    │      └───────────────┘
         │              │  (TurboPuffer)   │
         │              └──────────────────┘
         ▼
┌─────────────────┐
│ Message History │
└─────────────────┘
```

This architecture provides a robust foundation for building an intelligent, context-aware bot with memory, specialized capabilities, and excellent observability.