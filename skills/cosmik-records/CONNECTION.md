# network.cosmik.connection

a typed directed link between two cards. semble renders these as edges on the public knowledge graph.

## schema

```
{
  "from": {"uri": "at://did:plc:.../network.cosmik.card/3xxxxx"},
  "to":   {"uri": "at://did:plc:.../network.cosmik.card/3yyyyy"},
  "type": "<connection type, e.g. SUPPORTS, CONTRADICTS, RELATES_TO, EXTENDS>"
}
```

## connection types worth using

- `SUPPORTS` — `from` provides evidence or argument for `to`
- `CONTRADICTS` — `from` argues against or undermines `to`
- `EXTENDS` — `from` builds on `to` (a follow-up thought, a deeper case)
- `RELATES_TO` — weaker, generic association — use sparingly

if neither card has been written yet, write them first (you need both AT-URIs).

## minimum example

```
mcp__pdsx__create_record(
  collection="network.cosmik.connection",
  record={
    "from": {"uri": "at://did:plc:.../network.cosmik.card/3aaa"},
    "to":   {"uri": "at://did:plc:.../network.cosmik.card/3bbb"},
    "type": "SUPPORTS"
  }
)
```

## when not to make a connection

semble's vector search already surfaces semantically-related cards together. a connection is worth writing when the relationship is *specific and directional* — not just "these are about the same thing."

if you find yourself reaching for `RELATES_TO` constantly, that's a sign the cards are already adjacent in semantic space and the connection isn't doing real work.

## related

- `CARD-NOTE.md` — endpoint type 1
- `CARD-URL.md` — endpoint type 2
