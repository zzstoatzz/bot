# documentation

deeper dive into phi's design.

## contents

- [internal/operator-workflow.md](internal/operator-workflow.md) — current local operator path, private workflow receipts, and explicit migration boundaries

- [lore.md](lore.md) — dated background about the account, with who supplied each account

- [architecture.md](architecture.md) — entry points, scheduling, which model runs which agent, why this shape
- [memory.md](memory.md) — the four kinds of state phi draws on (thread, private, public, intent)
- [system-prompt.md](system-prompt.md) — block-by-block reference for what's actually in phi's context per run
- [mcp.md](mcp.md) — model context protocol integration
- [safety.md](safety.md) — how public actions are bounded: policies + judge, the pdsx guard, the operator override
- [testing.md](testing.md) — testing philosophy
- [observability.md](observability.md) — logfire integration and its sharp edges
- [skill-or-tool.md](skill-or-tool.md) — the principle for deciding when something is a tool vs a skill, with the review trail
- [tool-sprawl.md](tool-sprawl.md) — module-misplacement backlog from surfacing the catalogue in the UI
- [patterns.md](patterns.md) — recurring lessons from the git history (deletion, feedback loops, DotDict, voice vs structure, silently-empty blocks, prescription in task prompts, attention shapes voice)
- [lexicons.md](lexicons.md) — phi's custom `io.zzstoatzz.phi.*` schemas, how they're published, and the DNS authority record they need
- [internal/cockpit.md](internal/cockpit.md) — the web UI (internal, operator-facing)

- [internal/operator-consolidation-2026-09-19.md](internal/operator-consolidation-2026-09-19.md) — consolidation evidence, documentation audit, and verification

## proposed work

- [internal/waow-stewardship.md](internal/waow-stewardship.md) — waow.tech stewardship vision, gradual Gardener expansion, and the first offline jev evaluation milestone (2026-09-19; not deployed behavior)

- [internal/operator-interaction-design.md](internal/operator-interaction-design.md) — consolidate conversation, evidence, and scoped decisions before broader stewardship

- [internal/plyr-stewardship-2026-09-19.md](internal/plyr-stewardship-2026-09-19.md) — verified service inventory, capability gaps, cost/health limits, and the selected next expansion

- [internal/jev-microcosms-2026-09-19.md](internal/jev-microcosms-2026-09-19.md) — first real-provider pilot: corpus, held-out results, limitations, and decision to keep jev offline

- [internal/jev-historical-review-2026-09-19.md](internal/jev-historical-review-2026-09-19.md) — real Logfire examples, wrapper failure, historical routing fixes, and next semantic distinctions

- [internal/jev-purpose-results-2026-09-19.md](internal/jev-purpose-results-2026-09-19.md) — frozen historical-purpose evaluation and verified form-gate feedback fix

## reading order

1. **architecture.md** — overall shape
2. **memory.md** — what phi knows and where it lives
3. **system-prompt.md** — exactly what reaches the model on every run
4. **mcp.md** — external capabilities
5. **safety.md** — how public actions are bounded, and why structurally
6. **testing.md** — how we verify behavior
7. **skill-or-tool.md** — the design principle behind the tool/skill split
8. **tool-sprawl.md** — known module misplacements to clean up over time
9. **patterns.md** — recurring lessons; read before refactoring anything that looks accidental

each doc is self-contained and can be read independently.

these docs describe how phi works *now*. for how it came to work that way — the
incidents, the reversals, the reasoning that isn't in any diff — see
[../CHANGELOG.md](../CHANGELOG.md).
