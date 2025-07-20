# Penelope Bot Implementation Analysis

This is an analysis of Penelope, a Bluesky bot implementation by a Bluesky engineer (haileyok). The bot is written in Go and provides several key patterns and insights for building AT Protocol-compliant bots.

## Architecture Overview

### Core Components

1. **Main Entry Point** (`cmd/penelope/main.go`)
   - CLI-based application using `urfave/cli`
   - Configuration via environment variables or CLI flags
   - Graceful shutdown handling with OS signals
   - Metrics server on separate port for observability

2. **Core Bot Structure** (`penelope/penelope.go`)
   - Uses `xrpc.Client` for AT Protocol communication
   - Maintains authenticated session with automatic refresh
   - Thread-safe client access with RWMutex
   - ClickHouse integration for data persistence

### Key Design Patterns

#### 1. Event Handling Architecture

The bot uses a sophisticated event-driven architecture:

```go
// Parallel scheduler for handling events
scheduler := parallel.NewScheduler(400, 10, con.RemoteAddr().String(), rsc.EventHandler)
```

- **Parallel Processing**: Uses Indigo's parallel scheduler with 400 workers and 10 buffer size
- **Non-blocking**: Event handlers spawn goroutines for processing (`go p.repoCommit(ctx, evt)`)
- **Selective Processing**: Only processes create events, ignoring updates/deletes

#### 2. AT Protocol Connection Management

**WebSocket Connection to Firehose**:
```go
u.Path = "/xrpc/com.atproto.sync.subscribeRepos"
con, _, err := d.Dial(u.String(), http.Header{
    "user-agent": []string{"photocopy/0.0.0"},
})
```

**Key Features**:
- Connects to relay host (default: `wss://bsky.network`)
- Implements cursor persistence for resumption after restarts
- Uses CAR file format for reading repository data
- Validates CIDs to ensure data integrity

#### 3. Authentication & Session Management

**Initial Authentication**:
```go
resp, err := atproto.ServerCreateSession(ctx, x, &atproto.ServerCreateSession_Input{
    Identifier: args.BotIdentifier,
    Password:   args.BotPassword,
})
```

**Automatic Token Refresh**:
```go
go func() {
    ticker := time.NewTicker(1 * time.Hour)
    for range ticker.C {
        func() {
            p.xmu.Lock()
            defer p.xmu.Unlock()
            resp, err := atproto.ServerRefreshSession(ctx, p.x)
            if err != nil {
                p.logger.Error("error refreshing session", "error", err)
                return
            }
            p.x.Auth.AccessJwt = resp.AccessJwt
            p.x.Auth.RefreshJwt = resp.RefreshJwt
        }()
    }
}()
```

- Refreshes auth tokens every hour
- Thread-safe token updates
- Graceful error handling without crashing

#### 4. Conversation Flow & Reply Patterns

The bot implements a selective reply system:

```go
// Check if it's a reply
if rec.Reply == nil {
    return nil
}

// Check if replying to the bot
rootUri, _ := syntax.ParseATURI(rec.Reply.Root.Uri)
parentUri, _ := syntax.ParseATURI(rec.Reply.Parent.Uri)

if rootUri.Authority().String() != p.botDid && parentUri.Authority().String() != p.botDid {
    return nil
}
```

**Reply Logic**:
1. Only responds to posts that are replies
2. Checks if either the root or parent post is from the bot
3. Implements admin-only interaction model (see below)

#### 5. Admin User & Opt-in Model

**Critical Security Pattern**:
```go
// Admin check
if !slices.Contains(p.botAdmins, did) {
    return nil
}
```

- **Whitelist-based**: Only responds to pre-configured admin DIDs
- **No public interaction**: Prevents spam and abuse
- **Configurable**: Admin list provided via environment variable
- This is a key pattern for controlled bot rollouts

#### 6. Rate Limiting & Error Handling

**Built-in Protections**:
1. **HTTP Client Timeout**: 5-second timeout on all HTTP requests
2. **Cursor Persistence**: Saves cursor every 5 seconds to prevent data loss
3. **Error Isolation**: Each event processed in separate goroutine
4. **Graceful Degradation**: Logs errors but continues processing

**Event Size Handling**:
```go
if evt.TooBig {
    p.logger.Warn("commit too big", "repo", evt.Repo, "seq", evt.Seq)
    return
}
```

## Bluesky-Specific Patterns

### 1. Record Creation
```go
post := bsky.FeedPost{
    Text:      resp.Message.Content,
    CreatedAt: syntax.DatetimeNow().String(),
}

input := &atproto.RepoCreateRecord_Input{
    Collection: "app.bsky.feed.post",
    Repo:       p.botDid,
    Record:     &util.LexiconTypeDecoder{Val: &post},
}
```

- Uses proper Lexicon type decoder
- Includes required timestamp
- Specifies collection explicitly

### 2. URI Construction
```go
func uriFromParts(did string, collection string, rkey string) string {
    return "at://" + did + "/" + collection + "/" + rkey
}
```

- Follows AT URI scheme specification
- Used for referencing posts and records

### 3. Time Handling
Sophisticated time parsing with multiple fallbacks:
- Attempts to parse from record's CreatedAt
- Falls back to TID (timestamp ID) parsing
- Validates time ranges to prevent far-future/past timestamps
- Ultimate fallback to current time

## Integration Points

### 1. LLM Integration
Currently uses Ollama locally:
```go
url := "http://localhost:11434/api/chat"
request := ChatRequest{
    Model:    "gemma3:27b",
    Messages: []Message{message},
    Tools:    tools,
    Stream:   false,
}
```

### 2. Tool/Function Support
Implements a basic tool system:
- Currently only has `get_current_time` function
- Extensible architecture for adding more tools
- Function parsing from LLM responses

### 3. Data Persistence
Uses ClickHouse for:
- Likely for analytics and event storage
- High-performance time-series capabilities
- Could track interactions, metrics, etc.

## Key Takeaways for Python Implementation

1. **Event Processing Model**: Implement async/concurrent processing for firehose events
2. **Cursor Management**: Essential for production - persist cursor frequently
3. **Admin-only Mode**: Start with whitelist approach for safety
4. **Session Management**: Implement automatic token refresh
5. **Error Isolation**: Never let one bad event crash the entire stream
6. **Proper AT Protocol Types**: Use official SDK types and validators
7. **Rate Limiting**: Build in timeouts and backoff strategies
8. **Metrics/Observability**: Include metrics endpoint from the start

## Security Considerations

1. **Authentication**: Never log passwords or tokens
2. **Admin Control**: Whitelist approach prevents abuse
3. **Input Validation**: Validate all AT URIs and DIDs
4. **CID Verification**: Always verify content integrity
5. **Timeout Protection**: Prevent hanging on bad requests

This implementation serves as an excellent reference for production-grade Bluesky bots, emphasizing reliability, security, and proper AT Protocol compliance.