# Architecture model

`/architecture` maps the system around Phi. The semantic atlas remains a map of
remembered material, not a map of the software that handles it.

## Ownership and evidence

- `src/bot/core/architecture.json` owns reviewed component descriptions and
  directed semantic relationships. These describe material or control flow,
  not Python call order. Planned connections are explicit.
- `src/bot/core/architecture.py` parses the packaged Python source with AST:
  module/package inventory, absolute and relative internal imports, entry
  points, prompt functions and source line anchors. It lists runtime skills
  from disk. It never imports modules to discover their behavior.
- `/api/architecture` combines that structure with an allowlisted configuration
  summary. It does not read private memories, secrets, trace contents, or PDS
  records and does not check external service health. External source references
  describe reviewed repository contracts, not a verified remote deployment.
- `web/src/lib/architecture.ts` validates the response once. The Svelte page
  renders the same model as a desktop schematic and a mobile component browser.
  The source view exposes package dependencies separately from semantic flow.

The semantic connections need human review. Imports alone cannot establish that
an external Prefect flow publishes an atlas, that an override is operator-owned,
or that selecting an influence is not yet connected to prompt composition.
Source links follow repository main; discovered line numbers come from the
running release. The runtime may lack a repository-only file; references say so.

## Maintaining the map

When changing architecture, review the component and relationships in the same
change. Check source definitions before editing the model; preserve distinctions
between captured events, remembered accounts, projections, and execution evidence.
Add or retire nodes and edges as behavior changes. A planned edge must not become
implemented until the connection is actually shipped.

Run `just check` and the frontend checks/build. `tests/test_architecture.py`
verifies source paths and symbols, referential integrity, distinct storage
components, and the unconnected influence reader. It detects structural drift;
it does not prove the prose is true. Inspect the page at desktop and mobile
widths, including source search and navigating between related components.

## Path to Phi maintaining it

The manifest and renderer are independent. Phi can inspect both with the existing
own-source skill and use this model when proposing changes. A future maintenance
skill should require a before/after architecture diff alongside a code change,
retain links to evidence, and verify the rendered result. Updating the diagram
must not itself authorize code deployment, external mutations, or new access.
Phi does not currently modify or validate this page automatically.
