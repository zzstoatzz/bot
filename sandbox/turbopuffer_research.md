# Turbo Puffer Research for Bot Memory

## Overview
Turbo Puffer is a serverless vector database that's particularly well-suited for our bot use case because:
- **10x cheaper** than traditional vector DBs (uses S3 + SSD cache instead of RAM)
- **Scales to billions of vectors** with millions of namespaces
- **Fast search** with both vector similarity and full-text capabilities

## Key Features for Bot Memory

### 1. Namespace Support
- Perfect for user-specific memory partitions (like Marvin's approach)
- Can have millions of namespaces without performance degradation
- `copy_from_namespace` feature for template-based initialization

### 2. Performance
- 50% faster bulk upserts with base64 encoding
- Efficient filtering with range operators
- Smart caching on NVMe SSDs

### 3. Data Types
- UUID type (55% storage discount vs strings) - great for user/post IDs
- Bool type for flags
- Vector embeddings with similarity search

### 4. SDK Support
- Python SDK available (perfect for our FastAPI bot)
- TypeScript, Go, and Java also supported

## Architecture Benefits for Bluesky Bot

1. **Cost-Effective Scaling**: As the bot grows, memory costs stay manageable
2. **User Isolation**: Each user can have their own namespace
3. **Hybrid Search**: Combine semantic (vector) and keyword (full-text) search
4. **Serverless**: No infrastructure to manage

## Implementation Ideas

### User Memory Structure
```python
# Namespace per user
namespace = f"user_{user_did}"

# Store different types of memories
memories = {
    "facts": [],         # Semantic embeddings of facts
    "interactions": [],  # Previous conversation embeddings
    "preferences": [],   # User preferences as vectors
}
```

### Bot-Wide Memory
```python
# Global namespace for bot personality/knowledge
namespace = "bot_core"

# Store
- Personality traits as vectors
- Common responses
- Learned patterns
```

## Comparison with Reference Projects

| Feature | Marvin (Current) | Void (Letta) | Our Bot (TurboPuffer) |
|---------|------------------|---------------|----------------------|
| Storage | Vector store | Multi-tier blocks | Namespaced vectors |
| User Memory | Single namespace | Dynamic blocks | User namespaces |
| Scaling | Limited | Complex | Serverless/infinite |
| Cost | Higher | Medium | 10x cheaper |
| Search | Vector only | Archival search | Vector + full-text |

## Next Steps
1. Add `turbopuffer` to dependencies
2. Design memory schema (what to vectorize)
3. Implement memory manager service
4. Create embedding pipeline for conversations