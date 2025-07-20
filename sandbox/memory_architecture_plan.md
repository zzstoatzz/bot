# Memory Architecture Plan

## Overview
Using TurboPuffer for scalable vector memory with pydantic-ai agents.

## Memory Layers

### 1. Core Memory (Namespace: `bot_core`)
**Purpose**: Bot's persistent identity and knowledge
- Personality traits
- Core directives
- Communication style
- Self-knowledge

**Implementation**:
```python
core_memories = [
    "I am a helpful assistant on Bluesky",
    "I respond thoughtfully and concisely",
    "I remember conversations with users",
    # ... more core traits
]
```

### 2. User Memory (Namespace: `user_{did}`)
**Purpose**: Per-user context and history
- User facts and preferences
- Conversation summaries
- Interaction patterns
- Relationship context

**Example Structure**:
```python
UserMemory = {
    "facts": ["Works in tech", "Likes Python"],
    "last_interaction": "2024-07-20",
    "conversation_style": "technical, direct",
    "topics": ["programming", "AI"]
}
```

### 3. Conversation Memory (Namespace: `conversations`)
**Purpose**: Recent interaction context
- Thread summaries
- Recent exchanges
- Topic continuity

## Memory Flow

```
User mentions bot
    ↓
Load user memories (if exist)
    ↓
Retrieve relevant context
    ↓
Generate response with context
    ↓
Store new memories/facts
```

## TurboPuffer Integration

### Vector Embeddings
- Use OpenAI/Anthropic embeddings
- Store text + embedding pairs
- Semantic search for relevance

### Storage Schema
```python
Memory = {
    "id": "uuid",
    "text": "User likes Python programming",
    "type": "fact|conversation|trait",
    "user_did": "did:plc:xxx",
    "timestamp": "2024-07-20T10:00:00Z",
    "embedding": [0.1, 0.2, ...],  # 1536 dims
}
```

### Query Patterns
1. **User Context**: Get top-k relevant memories for user
2. **Topic Search**: Find memories related to current topic
3. **Time Decay**: Weight recent memories higher

## Pydantic-AI Agent Integration

### Memory-Aware Agent
```python
class BotAgent(BaseAgent):
    async def get_context(self, user_did: str, query: str):
        # 1. Load core memories
        # 2. Load user-specific memories
        # 3. Search for relevant context
        # 4. Return formatted context
        
    async def store_memory(self, user_did: str, memory: str):
        # 1. Generate embedding
        # 2. Store in TurboPuffer
        # 3. Update user namespace
```

### Context Injection
```python
system_prompt = f"""
{core_personality}

User Context:
{user_memories}

Recent Conversation:
{thread_context}
"""
```

## Future Considerations

### Memory Management
- Automatic summarization of old conversations
- Memory pruning/compression
- Importance scoring

### Advanced Features
- Cross-user pattern recognition
- Community memory (opt-in)
- Memory visualization endpoint

### Privacy
- User can request memory deletion
- No cross-contamination between users
- Transparent about what's remembered

## Next Steps
1. Set up TurboPuffer client
2. Create memory service
3. Integrate with pydantic-ai agent
4. Add memory management commands