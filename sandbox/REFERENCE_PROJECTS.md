# Reference Projects Analysis

## Void (Cameron Pfiffer)
- **Architecture**: Python with Letta/MemGPT for memory
- **Memory**: Dynamic block attachment system (zeitgeist, void-persona, void-humans, user blocks)
- **Key Features**: Tool-based memory management, git backups, queue-based processing
- **Lessons**: Memory as first-class entity, user-specific blocks, state synchronization challenges

## Penelope (Hailey)
- **Architecture**: Go with self-modification capabilities
- **Memory**: Core memory system with facts, Google search integration
- **Key Features**: Can update own profile, strong error handling, webhook-based
- **Lessons**: Self-modification patterns, robust Go error handling

## Marvin Slackbot (Prefect)
- **Architecture**: Python with multi-agent design, TurboPuffer vector DB
- **Memory**: User-namespaced vectors, conversation summaries
- **Key Features**: Task decomposition, progress tracking, multiple specialized agents
- **Lessons**: TurboPuffer usage patterns, namespace separation, SQLite for state

## What We Adopted
- Namespace-based memory organization (Marvin)
- User-specific memory storage (Void)
- Markdown personality files (general pattern)
- Profile self-modification (Penelope)
- Thread context tracking (all three)