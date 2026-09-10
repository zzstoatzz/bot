# cockpit (internal)

> **internal** — operator-facing surface. committed publicly like
> everything else, but not part of phi's advertised interface; expect
> rough edges and no stability promises.

the sveltekit app in `web/` (svelte 5, adapter-static), served by the
fastapi process at [phi.zzstoatzz.io](https://phi.zzstoatzz.io). pure
SPA: `ssr`/`prerender` disabled globally, unknown routes fall back to
`index.html` server-side and a styled `+error.svelte` client-side.

## surfaces

| route | what |
|---|---|
| `/` | recent published activity, current goals, stored-memory lookup, and a separate atlas overlay. Published activity is explicitly distinguished from unrecorded encounters. The typeahead palette opens a person’s logbook and original sources, including web evidence and non-Bluesky AT records. Long citation lists collapse; missing sources and unavailable replacement history are explicit. |
| `/docket` | daily promotion candidates from the docket flow |
| `/capabilities` | searchable skills and native tools from `/api/skills` and `/api/abilities`, with a compact index and a selected-detail pane. Phones show one view at a time; returning restores list position and focus. Partial reads and failures are explicit; MCP inventory is discovered separately during runs |
| `/market` | current season, holdings, season-limited net worth, past-season results, and dated trades. Inspect the line chart directly by pointer, touch, or arrow keys. Missing quotes stay missing; historical buys do not fabricate current holdings. Reads the bot’s `/api/chicken/*` proxy. |
| `/operator` | **operator override editor** — atproto OAuth login, write your `io.zzstoatzz.phi.override` record, see the live state phi obeys. see [../safety.md](../safety.md). current context (including working-guidance presence), tool use and public-check diagnostics follow the controls, with section links for mobile navigation. The September 8 voice capture is collapsed historical evidence. The **prompt cache** readout (`/api/cache`): one stacked bar per recent run — tokens read from cache / written at a premium / paid in full — plus collapse flags. public read, no auth |

`OverrideBanner` renders cockpit-wide when the operator's override is
active (public read of the record, ~60s cadence), linking to `/operator`.

The context panel distinguishes the cached base-context composition from
provider-measured usage in the runs included in that snapshot. The base
composition excludes task prompts and per-run blocks; it is not the full
starting context of a real run. Refresh failures leave the previous snapshot
visible with an explicit failure message. The operator form keeps its own
account-ownership rules regardless of the displayed usage data.

The shared HUD and reading panels use the Metroid Prime-inspired amber/cyan
palette, Saira Condensed chrome, Inter content, and JetBrains Mono references.
Selected navigation has dark text on an amber surface; form controls have
visible focus and touch targets. Operator diagnostics use the same palette.

## UI references

Before reshaping a surface, inspect the existing implementations:

- `race38/docs/ui-rigor.md` and `web/ballot.ts`: primary controls stay together,
  secondary editing collapses, obsolete requests cancel, and returning restores
  the viewer’s position. The checkout is `~/tangled.org/zzstoatzz.io/race38`.
- `typeahead/src/pages/home.ts` and `stats.ts`: compact search results and quiet
  metadata. Use race38’s keyboard interaction rather than copying the demo’s
  pointer-only result rows.
- `noti/src/render/styles.ts` and `actors.ts`: a thin surface highlight, shallow
  shadow, and compact avatar/name identity rows. Keep Phi’s own fonts and palette.
- `coral/site/style.css`: give the visualization the space and disclose supporting
  context around it. Pensieve’s `src/public/style.css` is another reference for
  restrained controls and full-width mobile detail.

The Mind atlas preview samples at most 600 real projected points and shares the
full atlas’s record-kind colors. It opens the existing atlas, not a second graph
implementation. Suggestions are a compact list; their full text remains in the
logbook. Account browsing still loads only when opened and displays 12 at a time.

## oauth notes

- browser flow (`@atproto/oauth-client-browser`), doodl's house pattern:
  static client metadata at `/oauth-client-metadata.json`, granular
  scope (`repo:io.zzstoatzz.phi.override?action=create&action=update`),
  `slingshot.microcosm.blue` for handle resolution. no bsky appview.
- **authz is repo ownership**: anyone can sign in and write the record
  to their own repo; the bot only reads the operator's (`owner_did`).
- localhost dev uses the atproto loopback client (metadata derived from
  the `client_id` query string; no hosted doc needed).
- historical trap: PDSes older than atproto PR #5147 (2026-06-25)
  reject same-site OAuth clients (`Sec-Fetch-Site: same-site`), which
  bites here because the cockpit and the operator's PDS share
  `zzstoatzz.io`. the operator's PDS runs a patched image — see
  `pds-infra`.

## dev

```bash
cd web && bun install && bun run dev   # vite proxies /api/* to the python server
bun run check                          # svelte-check
```

the docker build compiles `web/` in a bun stage and the fastapi app
mounts `web/build/` at `/` (see `src/bot/main.py` "frontend mount" for
the routing layering — explicit routes, then static, then SPA fallback).

## Exchange inspection

The user-view endpoint returns up to five recent stored reply pairs
alongside the exchange count, with original content, storage timestamp, and
source URIs. The detail drawer renders those rows and links to source posts.
`recent_interactions: null` means the read failed or the serving API lacks
this field; an empty array means that read succeeded with no rows. Legacy
rows without source URIs remain visible and identify their missing links.
This is bounded reply-pair history, not a complete encounter timeline.
