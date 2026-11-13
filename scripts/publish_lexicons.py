# /// script
# requires-python = ">=3.11"
# ///
"""Publish phi's lexicon schemas so `io.zzstoatzz.phi.*` NSIDs resolve.

Writes each `lexicons/**/*.json` as a `com.atproto.lexicon.schema` record
(rkey = the NSID) into phi's own repo. The NSID authority is every segment
but the last, reversed — `io.zzstoatzz.phi.self` is authored by
`phi.zzstoatzz.io` — so phi owns her own lexicons, the same way
`typeahead.waow.tech` owns `tech.waow.typeahead.*`.

Resolution needs a DNS TXT record at `_lexicon.phi.zzstoatzz.io` holding
`did=<phi's did>`. Without it the records exist but nothing can find them
from the NSID alone.

Usage (credentials are phi's own, already in .env):

    uv run scripts/publish_lexicons.py            # publish
    uv run scripts/publish_lexicons.py --dry-run  # show what would change

Idempotent: putRecord overwrites, so re-run after editing any lexicon.
"""

import asyncio
import json
import pathlib
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

from bot.config import settings  # noqa: E402
from bot.core import identity  # noqa: E402

LEXICON_DIR = pathlib.Path(__file__).parent.parent / "lexicons"
COLLECTION = "com.atproto.lexicon.schema"


def xrpc(pds: str, path: str, body: dict, token: str | None = None) -> dict:
    req = urllib.request.Request(
        f"{pds}/xrpc/{path}",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main() -> None:
    if unknown := set(sys.argv[1:]) - {"--dry-run"}:
        raise SystemExit(f"unknown arguments {sorted(unknown)}; nothing published")
    dry_run = "--dry-run" in sys.argv
    handle = settings.bluesky_handle
    password = settings.bluesky_password
    if not handle or not password:
        raise SystemExit("BLUESKY_HANDLE / BLUESKY_PASSWORD required")

    lexicons = sorted(LEXICON_DIR.rglob("*.json"))
    if not lexicons:
        raise SystemExit(f"no lexicons under {LEXICON_DIR}")

    # Every file's path must match its NSID, so the tree is browsable and a
    # typo in either shows up as a mismatch rather than a silent orphan.
    authorities = set()
    for path in lexicons:
        nsid = json.loads(path.read_text())["id"]
        expected = LEXICON_DIR / (nsid.replace(".", "/") + ".json")
        if path != expected:
            raise SystemExit(f"{path} declares id {nsid}; expected it at {expected}")
        authorities.add(".".join(reversed(nsid.split(".")[:-1])))

    print(f"{len(lexicons)} lexicons, authority: {', '.join(sorted(authorities))}")
    for authority in sorted(authorities):
        print(f"  DNS required: _lexicon.{authority}  TXT  did=<phi's did>")

    if dry_run:
        for path in lexicons:
            print(f"  would publish {json.loads(path.read_text())['id']}")
        return

    pds = asyncio.run(identity.pds_for_handle(handle))
    session = xrpc(
        pds,
        "com.atproto.server.createSession",
        {"identifier": handle, "password": password},
    )
    did = session["did"]
    token = session["accessJwt"]
    print(f"authenticated as {did} on {pds}\n")

    for path in lexicons:
        doc = json.loads(path.read_text())
        nsid = doc["id"]
        result = xrpc(
            pds,
            "com.atproto.repo.putRecord",
            {
                "repo": did,
                "collection": COLLECTION,
                "rkey": nsid,
                "record": {"$type": COLLECTION, **doc},
            },
            token,
        )
        print(f"published {nsid} -> {result['uri']}")

    print(f"\nnow point _lexicon.{sorted(authorities)[0]} TXT at did={did}")


if __name__ == "__main__":
    main()
