# documentation

References describe how Phi works now. Proposals describe work that is not
built. The archive holds dated audits, experiments and incident records; each
describes its own observation window and nothing later. Why things changed is
in the [changelog](../CHANGELOG.md).

## references

Read in this order for the overall picture.

1. [architecture.md](architecture.md) — entry points, scheduling, which model runs which agent. [architecture-map.md](architecture-map.md) covers the reviewed component model served at `/architecture`.
2. [memory.md](memory.md) — every context surface: purpose, when it was introduced, storage and recall.
3. [system-prompt.md](system-prompt.md) — block by block, what reaches the model on a run.
4. [mcp.md](mcp.md) — the MCP servers and how their tools are filtered and guarded.
5. [safety.md](safety.md) — how public actions are bounded: policies and judge, the pdsx guard, the operator override, private operator delivery.
6. [public-etiquette.md](public-etiquette.md) — what the judge reviews in a public post and what stays Phi's.
7. [patterns.md](patterns.md) — recurring lessons from the history. Read before refactoring anything that looks accidental.

By subsystem:

- [testing.md](testing.md) — what tests and evals each cover.
- [observability.md](observability.md) — Logfire integration and its sharp edges.
- [runtime-health.md](runtime-health.md) — `/health`, the watchdog and restarts.
- [lexicons.md](lexicons.md) — the `io.zzstoatzz.phi.*` schemas, how they are published, and the DNS record they need.
- [skill-or-tool.md](skill-or-tool.md) — how to decide whether a capability is a tool or a skill.
- [tool-sprawl.md](tool-sprawl.md) — tool consolidation that remains.
- [lore.md](lore.md) — dated background about the account, with who supplied each entry.

Operator-facing:

- [internal/operator-workflow.md](internal/operator-workflow.md) — how the operator works with Phi: the private conversation, workflow receipts, and what is not migrated.
- [internal/cockpit.md](internal/cockpit.md) — the web UI.

## proposals

- [inbound-messages.md](inbound-messages.md) — one shape for incoming messages and what rides along. The DM adapter ships; the rest is proposed.
- [internal/operator-interaction-design.md](internal/operator-interaction-design.md) — consolidate conversation, evidence and scoped decisions before broader stewardship.
- [internal/waow-stewardship.md](internal/waow-stewardship.md) — the waow.tech stewardship sequence. Not deployed.
- [internal/plyr-stewardship-next-step.md](internal/plyr-stewardship-next-step.md) — a plyr.fm evidence packet, deferred behind operator interaction design.

## archive

[archive/](archive/) by subject:

- Toolset: [September audit](archive/toolset-audit-2026-09.md), [October audit](archive/toolset-audit-2026-10.md).
- Memory: [Spotlight adoption](archive/spotlight-adoption-2026-10.md), [simplification plan](archive/memory-simplification.md), [goal design history](archive/goals-metabolism.md).
- Voice and personality: [voice calibration](archive/voice-calibration.md), [personality notes](archive/personality-notes-2026-09.md), [classifier audit](archive/classifier-audit-2026-09-06.md).
- State of the system: [status quo, September](archive/status-quo-2026-09.md), [closeout, September 5](archive/closeout-2026-09-05.md), [operator consolidation](archive/operator-consolidation-2026-09-19.md).
- jev evaluation: [microcosms pilot](archive/jev-microcosms-2026-09-19.md), [historical review](archive/jev-historical-review-2026-09-19.md), [purpose results](archive/jev-purpose-results-2026-09-19.md).
- Stewardship evidence: [plyr.fm inventory](archive/plyr-stewardship-2026-09-19.md), [Evergreen health survey](archive/evergreen-health-survey-2026-09-20.md).
- Incidents: [lexidraw process leak](archive/lexidraw-process-leak-2026-11-06.md).
