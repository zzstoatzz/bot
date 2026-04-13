# problem: exploration stores detailed profiles of spam accounts

## what's happening

phi's exploration pipeline researches unfamiliar accounts that appear in notifications or the For You feed. when it encounters a reply-spammer or content farm, it dutifully stores 5 detailed findings in turbopuffer — same as it would for a genuine person.

example from today: phi explored `coachchron.com` and stored 5 embeddings about their coaching brand, newsletter, pinned post, and reply-farming patterns. the exploration agent's own summary said "mass reply-farming, 25 replies within ~30 minutes, likely automated." phi correctly identified them as spam and then carefully filed away everything it learned about them.

this is wasteful in two ways:
- **storage cost**: 5 embeddings in turbopuffer for an account phi should never think about again
- **recall pollution**: those observations surface in future context when coachchron appears in a notification, burning embedding queries and attention budget on spam

## how exploration currently works

1. curiosity queue produces a work item (e.g. `explore_handle: coachchron.com`)
2. exploration agent runs with MCP tools — reads profile, posts, publications
3. agent returns `ExplorationResult`: up to 5 `ExplorationFinding`s, up to 2 follow-ups, a summary string
4. `process_exploration()` iterates all findings and stores each one unconditionally — per-user namespace if `target_handle` is set, episodic memory otherwise
5. queue item marked completed

there is no decision point between "the agent assessed this person" and "we store everything." the agent already reaches the right conclusion ("likely automated") but the pipeline doesn't act on it.

## relevant existing infrastructure

- `client.mute(actor: str) -> bool` — atproto SDK method, suppresses account from notifications and feeds. no unmute-on-restart risk since mute is a server-side record.
- `ExplorationResult.summary` — free-text field where the agent already writes assessments like "mass reply-farming." currently used only for logging.
- exploration prompt already says "if you find nothing worth noting, return empty findings." the agent doesn't apply this to spam accounts because it isn't told to.

## proposed design

**the exploration agent should decide whether an account is worth remembering.** it already does the research and reaches a conclusion — the pipeline just needs to respect that conclusion.

three changes:

### 1. add `mute_subject: bool` to ExplorationResult

```python
class ExplorationResult(BaseModel):
    findings: list[ExplorationFinding] = Field(...)
    follow_ups: list[dict] = Field(...)
    summary: str = Field(...)
    mute_subject: bool = Field(
        default=False,
        description="true if the subject is a spammer, bot farm, or content engine "
                    "not worth tracking. findings should be empty when this is true.",
    )
```

this is a structured signal from the agent, not a heuristic. the agent has already seen the profile, posts, and patterns — it's making a judgment call with evidence.

### 2. update exploration prompt

add to the exploration system prompt:

```
if the subject is a spammer, bot farm, or automated content engine — set mute_subject=true
and return empty findings. don't store detailed observations about accounts that aren't genuine.
the threshold is high: replying a lot is not spam. 25 generic replies in 30 minutes to strangers'
threads is.
```

### 3. update process_exploration to act on the signal

in `process_exploration()`, after the agent returns:

```python
if output.mute_subject and kind == "explore_handle":
    # mute so they don't appear in notifications/feeds again
    try:
        resolved = bot_client.client.resolve_handle(subject)
        bot_client.client.mute(resolved.did)
    except Exception as e:
        logger.warning(f"failed to mute {subject}: {e}")

    # store one line, not five — just enough to know we already dealt with them
    if self.memory:
        await self.memory.store_episodic_memory(
            content=f"muted @{subject} — {output.summary[:150]}",
            tags=["muted", "spam"],
            source="exploration",
        )

    await complete(rkey)
    return 0  # no findings stored, intentionally
```

when `mute_subject` is false, the existing flow is unchanged — findings stored as before.

## what this gets right

- **decision lives in the agent**, not in a heuristic. the same model that researches the account decides whether it's worth remembering. this is where the judgment should be — after seeing the evidence.
- **uses the platform's social tools**. mute is the correct atproto primitive for "i don't want to hear from this account." it's server-side, survives restarts, and is reversible (unmute exists).
- **one embedding instead of five** for spam accounts. enough to know "we already handled this" without detailed recall.
- **high threshold is built into the prompt**, not a numeric cutoff. "replying a lot is not spam. 25 generic replies in 30 minutes is."

## what could go wrong

- **false positive mutes**: phi mutes a genuine person who just happened to be noisy. mitigation: the threshold language in the prompt is deliberately conservative, and mute is reversible — the operator can unmute via the control API or directly.
- **mute accumulation**: over time phi mutes hundreds of accounts. this is probably fine — mute lists are lightweight on the PDS — but worth monitoring.
- **agent doesn't use the field**: the model might never set `mute_subject=true` because it's cautious. this is the safe failure mode — worst case is the status quo (5 findings stored for spammers).

## alternatives considered

- **post-exploration classifier**: a separate model or heuristic that reviews findings and decides whether to keep them. rejected because the exploration agent already has the context — adding a second pass is overhead for a decision that should happen at the source.
- **disposition enum (spam/genuine/unclear)**: more structured than a boolean, but the only actionable disposition is "mute." genuine and unclear both result in the same behavior (store findings). a three-way enum would be modeling a distinction without a difference.
- **block instead of mute**: block is stronger (prevents the account from seeing phi's posts) and creates a public record. mute is private and sufficient — phi just needs to stop hearing from them, not make a public statement.
