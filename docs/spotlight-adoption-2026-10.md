# spotlight memory adoption: waypoint, 2026-10-04

Percepta's [Spotlight Memory](https://www.percepta.ai/blog/spotlight-memory)
is a model architecture: a memory that grows with use, a constant-size read
and write per step, and addressing learned from the task. Phi runs on hosted
models, so none of it is adopted literally. What transfers is the shape. Each
store in [memory.md](memory.md) is read here as a memory with an address, a
write rule and a read size, and judged on the property the post measures most
sharply: after a value is rewritten, does the old one still come back
(MQAR-forgetting: Spotlight 0.998, attention 0.748, because attention keeps
both).

This is where adoption stands, store by store, and what was checked.

## turbopuffer

| | address | write rule | stale values |
|---|---|---|---|
| observation | handle, then nearest vectors | reconciled against the 3 nearest, every named row superseded | **narrowed 10-03** for new writes: closed for the rows the reconciler names among the 3 nearest. an unnamed neighbour, or a contradiction ranked 4th or lower, stays active. existing pairs merged |
| episodic note | nearest vectors | same reconciler | **narrowed 10-03** for new writes, same limit |
| run summary | nearest vectors | append only, by design: a run is an event | n/a |
| interaction | handle, then nearest vectors | append only | **open**: a superseded exchange still surfaces in `[PAST EXCHANGES]` |
| summary | handle | overwritten hourly while the author is in the mart | **closed 10-03**: not recalled once over 7 days old |

Shipped on 2026-10-03 (see the changelog for each):

- the reconciler reads three neighbours and now writes to every one it names,
  which is the post's "write the neighbourhood you read" (8fe39cc)
- the prefect `compact.py` likes phase reconciles the same way instead of
  adding blind (`my-prefect-server` 80cef2f, 1d644b5)
- the 284 near-duplicate active pairs that the old rule left behind were
  merged; 20 remain within cosine distance 0.25 (f976ed4, 64ec946)
- the episodic selector keeps its valid picks when it invents an index
  (30571cb)
- stale relationship summaries are no longer recalled (e9e9b2b)

## phi's PDS: intent state

`io.zzstoatzz.phi.{self,goal,persona}` are addressed by record key and
overwritten in place behind an owner gate or a judge. That is already the
delta rule: one cell per key, the new value replaces the old, and the old
version is not in the read path. `.atlas` and `.docket` are rebuilt daily from
the other stores. No stale-value gap was found here and nothing was changed.

The derived blobs lag: the atlas in production on 10-04 06:40 UTC was
generated 10-03 13:04 UTC, before the merge was applied that evening, so it
still projects the pre-merge rows until the next daily build.

## phi's PDS: the cosmik library (semble)

`network.cosmik.*` grows without bound and phi is its only writer. There is no
write-side reconcile: the cosmik-records skill asks her to check library
status before saving, and duplicate shelves have been created when the index
under-reported what the PDS held. Reads are constant size (collection names
and the five most recent cards in `[SEMBLE]`; search through the semble
tools). So this store has growing state and bounded reads, and its addressing
and overwrite are done by phi's judgment per call. Nothing was changed. It is
the store with the least mechanical protection against the stale-value
failure, and the one where a count of duplicate cards and shelves has not been
taken.

## what was checked in production, 2026-10-04 06:40 UTC

- release v637 (64ec946) complete, one machine started, health check passing;
  `/health` healthy with polling active
- `/api/diagnostic/context` renders `[GOALS]`, `[SELF]`, `[ATLAS]`,
  `[DOCKET]` and `[SEMBLE]` (9 collections, 196 cards, 39 connections) with no
  block errors
- `evals/test_reconciliation_targets.py` against the live extraction model:
  7 of 7
- Logfire since the fix deployed (10-03 08:43 UTC): the extractor ran twice at
  19:00 UTC and the reconciler ran once, at 15:01 UTC

Not checked: the content of that one reconciler decision. The natural path
has exercised the new prompt once; the weight of evidence for it is the eval
and the 190 decisions of the merge script, which ran the same reconciler from
a laptop. The per-author and episodic blocks are keyed by a batch and render
empty in the context preview, so they were not observed live either.

## next, in order

1. read reconciler decisions after a few days of extraction: how often it
   names more than one target, and whether supersessions jump
2. a forgetting replay eval: a fact that was later updated, where the old
   version must not surface. this is the measurement for the open interaction
   row
3. per-exchange source attribution in extraction (it is per chunk of 8 today),
   which the stale-exchange filter needs
4. count duplicate cards and shelves in the cosmik library before deciding
   whether it needs a write-side check
5. per-notification recall queries, then a coarse address for episodic before
   the vector search
