# skills + map enrichments

with the skills paradigm landed (pdsx-fundamentals + cosmik-records +
publish-blog) and `/api/users/{handle}` shipped, two follow-ons would
unblock the cockpit's map rework.

## 1. `GET /api/skills`

skills don't surface in the UI yet. they live in `bot/skills/{name}/` —
each with a `SKILL.md` whose frontmatter has `name` and `description`.

proposed endpoint:

```json
[
  {
    "name": "pdsx-fundamentals",
    "description": "How to use the pdsx MCP for atproto record CRUD on arbitrary lexicons. Load this when you want to do something on atproto that doesn't have a dedicated tool — saving to a custom lexicon, opening a tangled issue, writing a leaflet comment, etc.",
    "resources": ["SKILL.md"]
  },
  {
    "name": "cosmik-records",
    "description": "How to write to cosmik (your public knowledge graph on atproto via semble). Load this when you want to save a URL, write a public note, or create a typed connection between cards. The companion skill to pdsx-fundamentals — same mechanics, applied to the network.cosmik.* lexicons.",
    "resources": ["SKILL.md", "CARD-NOTE.md", "CARD-URL.md", "CONNECTION.md"]
  },
  {
    "name": "publish-blog",
    "description": "...",
    "resources": ["SKILL.md"]
  }
]
```

implementation: walk `bot/skills/`, parse the frontmatter from each
`SKILL.md`, list sibling `.md` files as `resources`. cache for process
lifetime; skills register at startup like tools do.

read path: `SkillsToolset(directories=[settings.skills_dir])` already
knows how to find them — you can probably introspect the toolset rather
than re-walking the directory.

UI consumer: skills get rendered on the `mind` lens as a kind of
"available capability" — alongside goals (anchors) and active
observations (current attention). nodes labeled by name; clicking
opens a logbook entry with the description and the resource list.

## 2. enrich `/api/memory/graph` with knowledge density

the new map design positions known people on a ring around phi. it
wants to scale each node by **knowledge density** — count of
non-superseded observations + summary presence — so dense relationships
look bigger than thin ones. that signal already exists in tpuf; today
the only way to get it from the UI is `/api/users/{handle}` per node,
which means N extra HTTP roundtrips on first map load.

proposal: add `density` to each user node returned by
`/api/memory/graph`:

```json
{
  "nodes": [
    {
      "id": "...",
      "label": "@samuel.fm",
      "type": "user",
      "x": 0.31, "y": -0.42,
      "density": 12,           // observation count (non-superseded)
      "has_summary": true      // whether a summary kind exists
    },
    ...
  ],
  "edges": [...]
}
```

`density` is the same `len(active observations)` the user-view endpoint
computes; you already have that pipeline. `has_summary` lets the UI
visually mark which people phi has a synthesized impression of vs.
people she only has scattered notes on.

with that, the cockpit map can render proper density-based sizing
without N parallel `/api/users/{handle}` calls on load. clicking still
fetches `/api/users/{handle}` for the rich logbook view.

## priority

`/api/skills` is the smaller change and unblocks the skills-as-map-kind
work. the `/api/memory/graph` enrichment is nice-to-have — the map can
ship without density (uniform sizing), then upgrade when the field
lands.
