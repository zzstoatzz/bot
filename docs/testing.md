# testing

phi uses behavioral testing with llm-as-judge evaluation.

## philosophy

**test outcomes, not implementation**

we care that phi:
- replies appropriately to mentions
- uses thread context correctly
- maintains consistent personality
- makes reasonable action decisions

we don't care:
- which exact HTTP calls were made
- internal state of the agent
- specific tool invocation order

## test structure

evals use a local `Response` output type (in `evals/conftest.py`) that predates the tool-based migration. production phi uses tool calls for actions and returns a plain summary string, but evals still want structured assertions on action/text.

## llm-as-judge

for subjective qualities (tone, relevance, personality), evals use claude as a judge to evaluate phi's responses against behavioral criteria.

## what we test

### unit tests
- memory operations (store/retrieve)
- thread context building
- response parsing

### integration tests
- full mention handling flow
- thread discovery
- decision making

### behavioral tests (evals)
- personality consistency
- thread awareness
- appropriate action selection
- memory utilization

## mocking strategy

**mock external services, not internal logic**

- mock ATProto client (don't actually post to bluesky)
- mock TurboPuffer (in-memory dict instead of network calls)
- mock MCP server (fake tool implementations)

**keep agent logic real** - we want to test actual decision making.

## running tests

```bash
just test        # unit tests
just evals       # behavioral tests with llm-as-judge
just check       # full suite (lint + typecheck + test)
```

## test isolation

tests never touch production:
- no real bluesky posts
- separate turbopuffer namespace for tests
- deterministic mock responses where needed

