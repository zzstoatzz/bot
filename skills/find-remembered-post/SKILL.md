---
name: find-remembered-post
description: Find a Bluesky post someone barely remembers from fragments, a possible author, or an approximate date. Check search coverage first and use the requester's likes to narrow candidates when they remember liking it.
---

Find the original post and give its link, exact wording, author and date. Treat
remembered wording, subject and timing as separate uncertain clues. A tentative
recognition is a lead, not confirmation; don't keep narrowing around an animal,
brand or phrase after the requester backs away from it.

## establish search coverage first

If using Pensieve or another personal index, check its freshness before searching:
read available build metadata, completion state and revision, and the newest
indexed post timestamp. Compare coverage with the remembered window and, where
available, current source records. A recent build time alone doesn't establish
current contents; a newest-post timestamp alone doesn't establish completeness.
Report stale, partial or unknown coverage before interpreting missing results.

Prefer an available authenticated API over browser sign-in. Phi currently has no
dedicated authenticated Pensieve tool. Do not invent one, treat a rendered landing
page as a search API, or request backend credentials to work around that gap.
When the index cannot be checked or misses the relevant period, use the public
record tools below. Finding a post does not require rebuilding an index.

## narrow by likes

When the requester says they probably liked the post, inspect their likes early.
For Nate, resolve `zzstoatzz.io`; its known DID is
`did:plc:xbtmt2zjwlrfegqvch7fboei`. Use the requester's repo explicitly: an omitted
repo can default to Phi's own account. Resolve a suspected author's DID too, then
filter each like's `subject.uri` by that author before fetching post bodies.

Use the pdsx read tools described in `pdsx-fundamentals`. For example:

```
list_records(collection="app.bsky.feed.like", repo="zzstoatzz.io", limit=100,
    select='.[] | {uri, subject: .value.subject.uri, likedAt: .value.createdAt}')
```

The response has `results` and `cursor`. Preserve the cursor and follow it even
when an author-filtered page has no matches. Keep the projection small; filtering
output reduces context, not the number of source pages that need examination.
On `response_too_large`, retry with its `retry_cursor` and a smaller projection
or limit before advancing. Checkpoint candidate URIs and the cursor so transient
failures don't require starting again.

Like time is not post time: someone can like an old post today. Verify pagination
direction from the returned records before applying a date stop, and start with
a generous window around the remembered encounter. Widen it if needed rather
than treating "two months ago" as a hard publication-date filter. State the
range actually scanned if stopping before exhaustion.

Deduplicate candidate subject URIs and hydrate with `read_posts`, up to 25 per
call. This returns text, author, timestamps, quote references and explicit missing
posts. Missing or deleted subjects remain unknown; don't call them nonmatches.
Search this small candidate set for both meaning and wording. Read quoted posts
and reply context when the remembered joke or media may be in the surrounding
conversation. Load `read-thread` when reading a conversation; inspect record
media when a textless post or screenshot could contain the clue.

Likes are a narrowing signal, not a requirement: a post can have been unliked,
liked from another account, or merely seen. If no candidate fits, use
`search_posts` with an author and a broad date range, or page the author's public
`app.bsky.feed.post` records. For public searches, vary the distinctive content
clue separately from generic stems like "has anyone tried" so the stem doesn't
dominate every result. Use semantic search when available; keyword absence isn't
semantic absence.

## present evidence without steering recall

Prefer one strong candidate over a growing list of weak ones. Show its wording
and canonical `https://bsky.app/profile/<did>/post/<rkey>` link. Say "you liked
this" only when a like record points to that exact post. Distinguish a strong
candidate from a requester-confirmed match; stop the search once confirmed.

The motivating search found an October 22, 2026 Norvid post in Nate's likes about
reshooting a Quiznos ad with a "biblically accurate elizabeth holmes furby".
Pensieve's newest indexed post was August 31. That dated example explains why
freshness and likes come first; it is not a current coverage claim or a default
topic for future searches.
