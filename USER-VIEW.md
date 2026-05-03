# user-view endpoint

the cockpit's `mind` lens currently shows generic copy when you click on a
handle node:

> "they're in my memory. that could mean we've exchanged messages, or it could
> mean i picked something up from a post nate liked — i can't tell from this
> view alone."

that's lackluster. it's also the wrong shape: the UI is supposed to be a
window into phi's *actual* experience of someone, not a placeholder. but i
won't fabricate a summary on the UI side via per-request LLM calls — that
would be the UI doing semantic work phi itself doesn't have access to. the
UI should only render state phi already maintains.

the question is therefore: what does phi actually carry about a person,
and can we surface it cleanly?

## what phi already has (no new state required)

the user's tpuf namespace (`phi-users-{clean_handle}`) already holds
everything we need:

| kind | source | what it is |
|---|---|---|
| `observation` | `extract_and_store` after conversation; compact's likes-derived extraction; review pass | atomic fact phi has noted about this person |
| `interaction` | `after_interaction` | verbatim turn — `user: ...\nbot: ...` |
| `summary` | the `compact` flow (in my-prefect-server) | synthesized relationship summary, written periodically |

phi reads all three live during conversation via
`NamespaceMemory.build_user_context(handle, query_text)` —
`namespace_memory.py:477`. so the contents are unambiguously phi-state.

`is_stranger(handle)` (`namespace_memory.py:1021`) returns true when the
namespace has fewer than 2 items. that's phi's own binary distinction
between "someone i know" and "someone new" — also real state.

## proposed endpoint

`GET /api/users/{handle}`

```json
{
  "handle": "samuel.fm",
  "did": "did:plc:...",            // null if not resolvable
  "is_stranger": false,            // is_stranger() result — phi's own threshold
  "counts": {
    "observation": 8,              // count where kind=observation, status!=superseded
    "interaction": 3,
    "summary": 1
  },
  "first_seen": "2026-03-12T...",  // earliest created_at across all kinds
  "last_seen":  "2026-04-29T...",  // latest created_at
  "summary": {                     // null if no summary kind exists
    "content": "...",              // the synthesized text compact wrote
    "created_at": "..."
  },
  "recent_observations": [         // top N by created_at desc, kind=observation
    {
      "content": "...",
      "tags": ["..."],
      "created_at": "...",
      "source_uris": ["at://..."]  // already stored on observations
    }
  ]
}
```

every field is a direct read of existing tpuf rows. no embedding, no LLM
call, no fabrication. cap `recent_observations` at ~5 for response size.

caching: tools registered at startup don't change, but the user view
*does* — fresh each request, or with a very short TTL (60s).

## why this is the right shape

- **histogram-as-counts**: gives the visual signal nate suggested
  ("how dense is phi's experience of this person") without inventing
  anything. zero observations + zero interactions = stranger; one summary
  + many interactions = a real relationship.
- **summary front-and-center**: compact already writes synthesized
  relationship summaries to tpuf. phi reads them as her own impression
  during conversation. surfacing the same string in the UI is just
  showing what phi shows herself.
- **recent observations**: the actual atomic facts. what phi *knows*
  about this person, written in phi's voice (because phi wrote them).
- **source_uris**: each observation already records the at-uris that
  produced it. the UI can link back to the conversation/post that
  formed each observation — provenance for free.

## what NOT to do

- don't run a haiku call per request to summarize on demand. the existing
  compact-written summary is the right artifact; if it's stale, the fix
  is to make compact run more often, not to pile UI-only synthesis on top.
- don't fetch arbitrary external data (bsky author feed, pub-search, etc.)
  into this endpoint. that's "phi could go look this up" — phi has tools
  for that. the user-view endpoint is "what phi *currently carries*."

## implementation hints

- in `bot/src/bot/main.py`, parallel to `/api/abilities`. reach the existing
  `NamespaceMemory` instance via `app.state.poller.handler.agent.memory`
  (it's already constructed in `PhiAgent.__init__`).
- methods that already exist or are trivially expressible: `is_stranger`,
  `get_knowledge_count`, `get_relationship_summary`. `counts` per kind is
  one tpuf query per kind with `top_k=1` and reading the total — or three
  count queries.
- handle the 404 case (namespace doesn't exist for this handle):
  return `{is_stranger: true, counts: {0,0,0}, summary: null, recent_observations: []}`.

## related thought (out of scope, raising for awareness)

phi could call this exact endpoint as a tool herself — `who_is(handle)` —
during conversation pre-flight. she'd get back the same view the UI
gets. that would replace `_maybe_lookup_stranger`'s author-lookup-via-bsky
with a memory-first equivalent. probably makes phi's first-touch behavior
better but it's a behavior change, not a UI change. flagging only.

## what the UI does once this lands

handle nodes in the `mind` atlas: on click, fetch
`/api/users/{handle}`, render in the logbook drawer:

- if `is_stranger`: small note saying so + the operator-likes context if
  it's also a discovery candidate.
- otherwise: the histogram (3 small counts), the summary if present,
  the most recent observations as a chronological list, first_seen /
  last_seen as a single line.

generic copy goes away.
