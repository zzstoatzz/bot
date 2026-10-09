# Skills and tools

A runtime skill describes a workflow. A tool performs an operation and enforces
its invariants. Before replacing a wrapper with instructions, identify which
validation, authorization, receipts or backend access would disappear.

## When a native tool earns its place

| Responsibility | Examples |
|---|---|
| Verify targets and enforce public-action policy | `post`, `write_bio`, `publish_blog_post` |
| Enforce operator authorization | `follow_user`, `propose_goal_change`, `write_self` |
| Preserve private memory versions and references | `save_memory`, `read_memory`, `retire_memory`, `restore_memory` |
| Access a backend or return model-readable content | Graze readers, `inspect_record_media`, `inspect_atlas` |
| Record delivery and distinguish uncertain outcomes | `report_operator`, `reply_operator_dm`, `request_workflow` |

A generic record API cannot replace these responsibilities with prose. Conversely,
a wrapper that only repeats schema guidance may belong in a skill. Cosmik wrappers
were removed on that basis; today's `cosmik-records` skill routes library work to
Semble's method discovery/calling tools, with standalone note-card writes through
pdsx. The MCP guard still applies to mutations.

`publish_blog_post` survived an earlier deletion proposal because it validates
publication, checks duplicates and records the result in episodic memory. The
`publish-blog` skill supplies the reading and composition workflow. These roles
complement each other; the skill is not a substitute for the publication gate.

## Names and discovery

Use verbs that distinguish operations. `save_memory` and `search_memory` replaced
ambiguous remember/recall names. Saved notes may enter automatic episodic recall
as well as explicit search; public Cosmik cards remain a different store.

Availability includes a usable discovery route. A hidden capability that a prompt
names directly is a broken contract. Deferred Tangled/Lexidraw tools are discoverable
through `search_tools`; runs whose tasks name Tangled tools load them outright.
The atlas tool description identifies the docket's record-media reader.

Low invocation counts require investigation: a control may be valuable precisely
because it is seldom needed, and a failed reader may look unused. The October
consolidation retained persona's automatic expiry after reviewing its history and
Phi's feedback, despite no recorded calls in the preceding 30 days.

The live `/api/abilities` and `/api/tool-usage` endpoints supply the catalogue and
usage evidence. See [tool consolidation](tool-sprawl.md) for remaining decisions,
[the surface map](memory.md) for purpose and provenance, and Git history for the
retired wrappers and earlier naming review. Historical tool inventories are not
current routing instructions.
