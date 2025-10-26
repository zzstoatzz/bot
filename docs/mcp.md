# mcp integration

phi uses the [model context protocol](https://modelcontextprotocol.io) to interact with bluesky.

## what is mcp

mcp is a protocol for connecting language models to external tools and data sources via a client-server architecture.

**why mcp instead of direct API calls?**
- clean separation: tools live in external server
- extensibility: add new tools without modifying agent
- reusability: same server can be used by other agents
- standard protocol: tools, resources, prompts

## architecture

```
PhiAgent (PydanticAI)
  ↓ stdio
ATProto MCP Server
  ↓ HTTPS
Bluesky API
```

the agent communicates with the MCP server via stdio. the server handles all bluesky API interactions.

## available tools

from the ATProto MCP server:

- `post(text, reply_to?, quote?)` - create posts and replies
- `like(uri)` - like a post
- `repost(uri)` - share a post
- `follow(handle)` - follow a user
- `search(query)` - search posts
- `create_thread(posts)` - create multi-post threads

## how it works

1. agent decides to use a tool (e.g., "i should reply")
2. pydantic-ai sends tool call to MCP server via stdio
3. MCP server executes bluesky API call
4. result returned to agent
5. agent continues with next action

## agent configuration

```python
# src/bot/agent.py
agent = Agent(
    "claude-3-5-sonnet-20241022",
    deps_type=AgentDeps,
    result_type=Response,
    system_prompt=personality,
)

# mcp server connected via stdio
mcp = MCPManager()
mcp.add_server(
    name="atproto",
    command=["uvx", "atproto-mcp"],
    env={"BLUESKY_HANDLE": handle, "BLUESKY_PASSWORD": password}
)

# tools exposed to agent
async with mcp.run() as context:
    for tool in context.list_tools():
        agent.register_tool(tool)
```

## structured outputs

agent returns typed responses instead of using tools directly:

```python
class Response(BaseModel):
    action: Literal["reply", "like", "repost", "ignore"]
    text: str | None = None
    reason: str | None = None
```

message handler interprets the response and executes via MCP tools if needed.

**why structured outputs?**
- clear contract between agent and handler
- easier testing (mock response objects)
- explicit decision tracking
- agent focuses on "what to do", handler focuses on "how to do it"
