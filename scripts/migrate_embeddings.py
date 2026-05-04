"""Migrate phi tpuf vectors from text-embedding-3-small (1536 dims) to voyage embeddings.

Default behavior is DRY-RUN: prints the migration plan + estimated token
cost without writing or calling voyage. Pass --execute to actually run.

Usage:
    # dry-run, all phi-* namespaces
    uv run --with voyageai scripts/migrate_embeddings.py

    # one namespace only (still dry-run)
    uv run --with voyageai scripts/migrate_embeddings.py --namespace phi-users-iami_earth

    # actually do the migration
    VOYAGE_API_KEY=... uv run --with voyageai scripts/migrate_embeddings.py --execute

    # different voyage model / dimension
    uv run --with voyageai scripts/migrate_embeddings.py --model voyage-4 --dimension 1024

After successful migration, manually:
1. Update bot/src/bot/memory/namespace_memory.py to use voyage embeddings + the
   new namespace names (NAMESPACES constant + the embed call site).
2. Smoke-test in production.
3. Once verified, drop the v1 namespaces (separate cleanup step — destructive,
   left out of this script intentionally).
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

from turbopuffer import Turbopuffer

from bot.config import settings

DEFAULT_MODEL = "voyage-4-lite"
DEFAULT_DIMENSION = 1024
DEFAULT_BATCH_SIZE = 100
DEFAULT_SUFFIX = "-v2"

# Namespaces actively read/written by the live code. Anything not listed here
# (phi-core, phi-tag-*, phi-threads-*) is orphaned data from old experiments —
# verified by grepping the codebase: zero references. Skipping by default.
LIVE_PHI_NAMESPACES = ("phi-episodic", "phi-observations")
LIVE_PHI_PREFIXES = ("phi-users-",)

# Schemas — copied from bot/src/bot/memory/extraction.py so the migration is
# self-contained (no import dependency on internal layout). If those schemas
# change, update here too.
USER_NAMESPACE_SCHEMA = {
    "kind": {"type": "string", "filterable": True},
    "status": {"type": "string", "filterable": True},
    "content": {"type": "string", "full_text_search": True},
    "tags": {"type": "[]string", "filterable": True},
    "supersedes": {"type": "string"},
    "source_uris": {"type": "[]string"},
    "created_at": {"type": "string"},
    "updated_at": {"type": "string"},
}
EPISODIC_SCHEMA = {
    "content": {"type": "string", "full_text_search": True},
    "tags": {"type": "[]string", "filterable": True},
    "source": {"type": "string", "filterable": True},
    "source_uris": {"type": "[]string"},
    "created_at": {"type": "string"},
}

# Attributes we care about preserving on every row. We pull them generously;
# rows with missing attrs simply omit them.
PRESERVE_ATTRS = (
    "kind",
    "status",
    "content",
    "tags",
    "supersedes",
    "source_uris",
    "created_at",
    "updated_at",
    "source",
)


@dataclass
class NamespacePlan:
    name: str
    target_name: str
    rows: list[dict]
    estimated_tokens: int


def schema_for_namespace(ns_id: str) -> dict:
    """Pick the schema based on namespace ID convention.

    User namespaces and the observation archive use USER_NAMESPACE_SCHEMA;
    the rest (episodic, core, threads, tag) use EPISODIC_SCHEMA.
    """
    if ns_id.startswith("phi-users-") or ns_id == "phi-observations":
        return USER_NAMESPACE_SCHEMA
    return EPISODIC_SCHEMA


def list_phi_namespaces(client: Turbopuffer) -> list[str]:
    """List the namespaces the live code actually uses, paginating tpuf if needed.

    Filters to per-user namespaces + the two system namespaces (episodic,
    observations). Dead namespaces from old experiments (phi-core,
    phi-tag-*, phi-threads-*) are excluded — they're not referenced
    anywhere in the codebase and migrating them would be wasted work.
    """
    found: list[str] = []
    page = client.namespaces()
    while True:
        for ns in page.namespaces:
            if ns.id in LIVE_PHI_NAMESPACES or any(
                ns.id.startswith(p) for p in LIVE_PHI_PREFIXES
            ):
                found.append(ns.id)
        cursor = getattr(page, "next_cursor", None)
        if not cursor:
            break
        page = client.namespaces(cursor=cursor)
    return sorted(found)


def collect_rows(client: Turbopuffer, ns_id: str) -> list[dict]:
    """Read all rows from a namespace with their attributes (no vectors).

    Tries the standard `rank_by=("created_at", "desc")` first; if the
    namespace was written with a schema that doesn't include created_at
    (older phi memory or other projects' namespaces), falls back to
    `rank_by=("id", "desc")` which always works.
    """
    namespace = client.namespace(ns_id)
    try:
        response = namespace.query(
            rank_by=("created_at", "desc"),
            top_k=10_000,
            include_attributes=True,
        )
    except Exception:
        # attribute may not exist on this namespace; rank by id instead
        response = namespace.query(
            rank_by=("id", "desc"),
            top_k=10_000,
            include_attributes=True,
        )
    rows: list[dict] = []
    for row in response.rows or []:
        data: dict = {"id": row.id}
        for attr in PRESERVE_ATTRS:
            val = getattr(row, attr, None)
            if val is not None:
                data[attr] = val
        rows.append(data)
    return rows


def estimate_tokens(text: str) -> int:
    """Rough char-to-token estimate. Voyage tokenizer is BPE; ~4 chars/token avg."""
    return max(1, len(text) // 4)


def build_plan(
    client: Turbopuffer, namespace_filter: str | None, suffix: str
) -> list[NamespacePlan]:
    if namespace_filter:
        namespaces = [namespace_filter]
    else:
        namespaces = list_phi_namespaces(client)

    plans: list[NamespacePlan] = []
    for ns_id in namespaces:
        rows = collect_rows(client, ns_id)
        token_est = sum(estimate_tokens(r.get("content", "")) for r in rows)
        plans.append(
            NamespacePlan(
                name=ns_id,
                target_name=ns_id + suffix,
                rows=rows,
                estimated_tokens=token_est,
            )
        )
    return plans


def print_plan(
    plans: list[NamespacePlan], suffix: str, model: str, dimension: int
) -> None:
    print("=== migration plan ===")
    print(f"target embedding: {model} @ {dimension} dims")
    print(f"namespace suffix: {suffix}")
    print()
    print(f"{'namespace':<55} {'rows':>6} {'~tokens':>10}")
    print("-" * 75)
    total_rows = 0
    total_tokens = 0
    empty_count = 0
    for p in plans:
        marker = " (empty)" if not p.rows else ""
        print(f"{p.name:<55} {len(p.rows):>6} {p.estimated_tokens:>10}{marker}")
        total_rows += len(p.rows)
        total_tokens += p.estimated_tokens
        if not p.rows:
            empty_count += 1
    print("-" * 75)
    print(f"{'TOTAL':<55} {total_rows:>6} {total_tokens:>10}")
    print()
    if empty_count:
        print(f"({empty_count} empty namespaces will be skipped)")
    voyage_free = 200_000_000  # voyage-4 family one-time free allowance per account
    if total_tokens < voyage_free:
        pct = (total_tokens / voyage_free) * 100
        print(
            f"voyage-4 family free allowance: 200M tokens. estimated usage: {pct:.4f}% of cap. cost: $0."
        )
    else:
        billable = total_tokens - voyage_free
        print(f"exceeds 200M free allowance by {billable:,} tokens — billable.")


def embed_batch(
    voyage_client, texts: list[str], model: str, dimension: int
) -> list[list[float]]:
    """Call voyage to embed a batch. Returns one vector per text, in order."""
    result = voyage_client.embed(
        texts=texts,
        model=model,
        input_type="document",
        output_dimension=dimension,
    )
    return result.embeddings


def migrate_namespace(
    client: Turbopuffer,
    voyage_client,
    plan: NamespacePlan,
    model: str,
    dimension: int,
    batch_size: int,
) -> int:
    """Re-embed all rows in plan and write to plan.target_name. Returns row count written."""
    if not plan.rows:
        return 0

    target = client.namespace(plan.target_name)
    schema = schema_for_namespace(plan.name)
    written = 0

    for batch_start in range(0, len(plan.rows), batch_size):
        batch = plan.rows[batch_start : batch_start + batch_size]
        # Voyage refuses empty strings; substitute a single space so the
        # row still gets a vector and the surrounding metadata is preserved.
        texts = [(r.get("content") or " ") for r in batch]
        vectors = embed_batch(voyage_client, texts, model, dimension)
        upsert_rows = []
        for row, vec in zip(batch, vectors, strict=True):
            row_data = {**row, "vector": vec}
            upsert_rows.append(row_data)
        # New namespaces need the distance metric specified on first write —
        # mirrors the same arg passed everywhere in namespace_memory.py.
        target.write(
            upsert_rows=upsert_rows,
            schema=schema,
            distance_metric="cosine_distance",
        )
        written += len(batch)
        print(f"    {plan.name}: {written}/{len(plan.rows)}")
    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the migration (default is dry-run).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Voyage model (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--dimension",
        type=int,
        default=DEFAULT_DIMENSION,
        help=f"Output dimension (default: {DEFAULT_DIMENSION})",
    )
    parser.add_argument(
        "--suffix",
        default=DEFAULT_SUFFIX,
        help=f"Suffix for new namespace names (default: {DEFAULT_SUFFIX})",
    )
    parser.add_argument("--namespace", help="Migrate only this specific namespace ID")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Rows per voyage embed call (default: {DEFAULT_BATCH_SIZE}, max 1000 per voyage limit)",
    )
    args = parser.parse_args()

    client = Turbopuffer(
        api_key=settings.turbopuffer_api_key,
        region=settings.turbopuffer_region,
    )
    print(f"connected to tpuf, region={settings.turbopuffer_region}")
    print("building plan...")
    plans = build_plan(client, args.namespace, args.suffix)
    print_plan(plans, args.suffix, args.model, args.dimension)

    if not args.execute:
        print()
        print("DRY RUN — pass --execute to actually run the migration.")
        return

    voyage_key = settings.voyage_api_key or os.environ.get("VOYAGE_API_KEY")
    if not voyage_key:
        print(
            "ERROR: voyage_api_key not set. Add VOYAGE_API_KEY to .env or env.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        import voyageai
    except ImportError:
        print(
            "ERROR: voyageai not installed. Run with: uv run --with voyageai scripts/migrate_embeddings.py --execute",
            file=sys.stderr,
        )
        sys.exit(1)

    voyage_client = voyageai.Client(api_key=voyage_key)

    print()
    print("=== executing migration ===")
    total_written = 0
    for i, plan in enumerate(plans, 1):
        print(
            f"[{i}/{len(plans)}] {plan.name} -> {plan.target_name} ({len(plan.rows)} rows)"
        )
        if not plan.rows:
            print("    (empty, skipping)")
            continue
        try:
            written = migrate_namespace(
                client, voyage_client, plan, args.model, args.dimension, args.batch_size
            )
            total_written += written
        except Exception as e:
            print(f"    FAILED: {e}", file=sys.stderr)
            print(
                f"    leaving {plan.target_name} in whatever state it reached; safe to re-run",
                file=sys.stderr,
            )

    print()
    print(f"=== done. {total_written} rows written across {len(plans)} namespaces. ===")
    print()
    print("next steps:")
    print(" 1. update bot/src/bot/memory/namespace_memory.py:")
    print("    - swap _get_embedding to call voyage instead of OpenAI")
    print(f"    - update NAMESPACES constants to reference the new {args.suffix} names")
    print(" 2. add voyageai to pyproject.toml + uv sync")
    print(" 3. set VOYAGE_API_KEY as a fly secret + restart")
    print(" 4. smoke-test in production")
    print(" 5. once stable, drop the v1 namespaces (manual or a separate script)")


if __name__ == "__main__":
    main()
