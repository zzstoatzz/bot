# Project Status

## Current Phase: Initial Setup

### Completed
- ✅ Created project directory structure (.eggs, tests, sandbox)
- ✅ Cloned reference projects:
  - penelope (Bluesky bot in TypeScript)
  - void (Digital personhood exploration on Bluesky)
  - marvin/slackbot (Python bot example)

### In Progress
- 🔄 Analyzing reference projects for architectural insights
- 🔄 Setting up core dependencies

### Next Steps
1. Add core dependencies (FastAPI, Bluesky/AT Protocol SDK, LLM libraries)
2. Create justfile for development workflow
3. Design bot architecture based on reference projects
4. Implement basic FastAPI structure
5. Set up Bluesky integration

## Key Decisions to Make
- Which LLM provider to use (OpenAI, Anthropic, etc.)
- Bot personality and behavior design
- Hosting and deployment strategy
- Response generation approach (streaming vs batch)

## Reference Projects Analysis
- **penelope**: Go-based with core memory, self-modification, and Google search capabilities
- **void**: Python/Letta with sophisticated 3-tier memory and strong personality consistency
- **marvin slackbot**: Multi-agent architecture with TurboPuffer vector memory and progress tracking

### Key Insights from Deep Dive
- All three bots have memory systems (not just Void)
- Penelope can update its own profile and has "core memory"
- Marvin uses user-namespaced vectors in TurboPuffer
- Deployment often involves separate GPU machines for LLM
- HTTPS/CORS handling is critical for remote deployments