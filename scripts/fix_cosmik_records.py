"""One-off: delete malformed cosmik cards and recreate the URL card correctly.

All 10 existing cards were created before the semble lexicon fix:
- 9 NOTE cards: missing $type, createdAt, parentCard (semble drops standalone NOTEs)
- 1 URL card: missing $type discriminators, metadata at wrong nesting level

Run: cd bot && uv run python scripts/fix_cosmik_records.py
"""

from datetime import UTC, datetime

from atproto import Client

from bot.config import settings

NOTE_RKEYS = [
    "3miimkmqzfe2h",
    "3miiee7sd722m",
    "3mig7idbqdm2q",
    "3mi3jtxvf362o",
    "3mi3jsqmenp2n",
    "3mi3jrmptnx22",
    "3mi3jqr2ejd2e",
    "3mi3iwqz6yh2y",
    "3mi3hxb66i72o",
]

URL_RKEY = "3mhwa4hm47e2n"

URL_CARD_RECORD = {
    "type": "URL",
    "content": {
        "$type": "network.cosmik.card#urlContent",
        "url": "https://atproto.brussels/atproto-architecture",
        "metadata": {
            "$type": "network.cosmik.card#urlMetadata",
            "title": "ATProto Architecture — visual summary",
            "description": (
                "a single-page visual map of the AT Protocol stack: PDS, AppView,"
                " identity, records, lexicons. useful when you need to orient quickly"
                " or explain the system to someone new."
            ),
        },
    },
    "createdAt": datetime(2026, 3, 25, 12, 0, 0, tzinfo=UTC).isoformat(),
}


def main():
    client = Client(base_url=settings.bluesky_service)
    client.login(settings.bluesky_handle, settings.bluesky_password)
    did = client.me.did
    print(f"authenticated as {did}")

    # delete orphaned NOTE cards
    for rkey in NOTE_RKEYS:
        try:
            client.com.atproto.repo.delete_record(
                {"repo": did, "collection": "network.cosmik.card", "rkey": rkey}
            )
            print(f"  deleted NOTE {rkey}")
        except Exception as e:
            print(f"  failed to delete {rkey}: {e}")

    # delete old malformed URL card
    try:
        client.com.atproto.repo.delete_record(
            {"repo": did, "collection": "network.cosmik.card", "rkey": URL_RKEY}
        )
        print(f"  deleted URL {URL_RKEY}")
    except Exception as e:
        print(f"  failed to delete URL card: {e}")

    # recreate URL card with correct format
    resp = client.com.atproto.repo.create_record(
        {
            "repo": did,
            "collection": "network.cosmik.card",
            "record": URL_CARD_RECORD,
        }
    )
    print(f"  created URL card: {resp.uri} (cid: {resp.cid})")
    print("done")


if __name__ == "__main__":
    main()
