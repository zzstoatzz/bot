# Void's Memory System Analysis

## Overview

Void uses Letta (formerly MemGPT) for a sophisticated dynamic memory system. The key innovation is **dynamic block attachment** - memory blocks are attached/detached based on who the bot is talking to.

## Core Memory Architecture

### Three Persistent Memory Blocks
1. **zeitgeist** - Current understanding of social environment
2. **void-persona** - The agent's evolving personality  
3. **void-humans** - General knowledge about humans it interacts with

### Dynamic User Blocks
- **user_{handle}** - Per-user memory blocks created on demand
- Attached when conversing with that user
- Detached after the conversation
- Persisted between conversations

## How Dynamic Attachment Works

### 1. Notification Processing
```python
# When a notification comes in, extract all handles from the thread
unique_handles = extract_handles_from_data(thread_data)

# Attach memory blocks for all participants
attach_result = attach_user_blocks(unique_handles, void_agent)
```

### 2. Block Creation/Attachment
- Check if block exists for user (by label: `user_{clean_handle}`)
- If not, create with default content: `"# User: {handle}\n\nNo information about this user yet."`
- Attach block to agent's current context
- Block has 5000 character limit

### 3. During Conversation
- Agent has access to:
  - Core blocks (zeitgeist, void-persona, void-humans)
  - All attached user blocks for thread participants
- Agent can modify blocks via tools:
  - `user_note_append` - Add information
  - `user_note_replace` - Update information
  - `user_note_set` - Replace entire block
  - `user_note_view` - Read block contents

### 4. After Processing
```python
# Detach all user blocks to keep context clean
detach_result = detach_user_blocks(attached_handles, void_agent)
```

## Key Design Decisions

### Why Dynamic Attachment?
1. **Context Management** - Only load relevant user memories
2. **Scalability** - Can handle thousands of users without loading all memories
3. **Privacy** - User A's memories aren't accessible when talking to User B
4. **State Clarity** - Agent knows exactly who is in the conversation

### Block Persistence
- Blocks persist in Letta's storage even when detached
- Next conversation with user reattaches their existing block
- Enables long-term relationship building

### Tool-Based Modification
- Memory updates happen through explicit tool calls
- Agent must decide to remember something
- Creates audit trail of memory modifications
- Prevents accidental memory corruption

## Challenges and Considerations

### 1. State Synchronization
- Must track which blocks are attached
- Careful cleanup required after each interaction
- Risk of blocks staying attached if errors occur

### 2. Character Limits
- Each block limited to 5000 characters
- No automatic summarization/compression
- Agent must manage space within blocks

### 3. Multi-User Threads
- Attaches blocks for ALL participants
- Can lead to many blocks in context
- May hit token limits with large threads

### 4. Performance
- Block attachment/detachment has API overhead
- Each operation is atomic but sequential
- Can slow down response time

## Comparison to Phi's Approach

### Void (Dynamic)
- Blocks attached/detached per conversation
- Explicit memory management
- Complex but flexible
- Requires Letta infrastructure

### Phi (Static Namespaces)  
- All memories always accessible via namespaces
- Queries fetch relevant memories
- Simple but potentially less focused
- Direct TurboPuffer integration

## Key Insights

1. **Memory as First-Class Entity** - Memories are explicit blocks the agent can inspect and modify
2. **Contextual Loading** - Only load memories relevant to current conversation
3. **Tool-Accessible** - Agent can actively manage its own memory
4. **Relationship Persistence** - Each user relationship maintained separately

The dynamic attachment pattern is powerful but complex. It enables sophisticated memory management at the cost of additional infrastructure and state management overhead.