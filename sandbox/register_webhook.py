"""Register a wisp.place webhook for mention backlinks.

Usage:
    uv run python scripts/register_webhook.py <webhook-url>
    uv run python scripts/register_webhook.py --list
    uv run python scripts/register_webhook.py --delete <rkey>
"""

import sys
from datetime import datetime, timezone

from atproto import Client

from bot.config import settings


def main():
    client = Client(base_url=settings.bluesky_service)
    client.login(settings.bluesky_handle, settings.bluesky_password)
    did = client.me.did
    print(f"authenticated as {settings.bluesky_handle} ({did})")

    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        result = client.com.atproto.repo.list_records(
            params={"repo": did, "collection": "place.wisp.v2.wh", "limit": 50}
        )
        if not result.records:
            print("no webhooks registered")
            return
        for rec in result.records:
            rkey = rec.uri.split("/")[-1]
            val = rec.value if isinstance(rec.value, dict) else vars(rec.value) if hasattr(rec.value, '__dict__') else str(rec.value)
            print(f"  [{rkey}] {val}")
        return

    if len(sys.argv) > 2 and sys.argv[1] == "--delete":
        rkey = sys.argv[2]
        client.com.atproto.repo.delete_record(
            data={"repo": did, "collection": "place.wisp.v2.wh", "rkey": rkey}
        )
        print(f"deleted webhook {rkey}")
        return

    url = sys.argv[1] if len(sys.argv) > 1 else None
    if not url:
        print(__doc__)
        sys.exit(1)

    record = {
        "$type": "place.wisp.v2.wh",
        "scope": {
            "aturi": f"at://{did}",
            "backlinks": True,
        },
        "url": url,
        "events": ["create"],
        "enabled": True,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }

    if settings.wisp_webhook_secret:
        record["secret"] = settings.wisp_webhook_secret
        print("using HMAC secret from WISP_WEBHOOK_SECRET")

    result = client.com.atproto.repo.create_record(
        data={
            "repo": did,
            "collection": "place.wisp.v2.wh",
            "record": record,
        }
    )

    print(f"webhook registered: {result.uri}")
    print(f"  url: {url}")
    print(f"  scope: at://{did} (backlinks)")
    print(f"  events: create")


if __name__ == "__main__":
    main()
