"""Phi's goals — durable anchors stored on PDS.

Each goal is a single record under `io.zzstoatzz.phi.goal`. Updates use
putRecord with the same rkey, so the goal evolves in place over time.
History is in the firehose if anyone wants it.

Mutation is gated at the tool layer (propose_goal_change) using the same
_is_owner check as follow_user — so phi can only change its own goals
when the owner has just liked an authorization-request post.
"""

from datetime import UTC, datetime

from bot.core.atproto_client import BotClient

GOAL_COLLECTION = "io.zzstoatzz.phi.goal"


async def list_goals(client: BotClient) -> list[dict]:
    """Read all goal records from phi's PDS. Each result includes _rkey."""
    await client.authenticate()
    if not client.client.me:
        return []
    try:
        response = client.client.com.atproto.repo.list_records(
            {
                "repo": client.client.me.did,
                "collection": GOAL_COLLECTION,
                "limit": 20,
            }
        )
        out = []
        for rec in response.records:
            value = dict(rec.value)
            value["_rkey"] = rec.uri.split("/")[-1]
            out.append(value)
        return out
    except Exception:
        return []


async def get_goal(client: BotClient, rkey: str) -> dict | None:
    await client.authenticate()
    if not client.client.me:
        return None
    try:
        response = client.client.com.atproto.repo.get_record(
            params={
                "repo": client.client.me.did,
                "collection": GOAL_COLLECTION,
                "rkey": rkey,
            }
        )
        return dict(response.value) if response.value else None
    except Exception:
        return None


async def upsert_goal(
    client: BotClient,
    rkey: str | None,
    title: str,
    description: str,
    progress_signal: str,
) -> str:
    """Create (rkey=None) or update an existing goal. Returns AT-URI."""
    await client.authenticate()
    assert client.client.me is not None
    now = datetime.now(UTC).isoformat()
    record: dict = {
        "title": title,
        "description": description,
        "progress_signal": progress_signal,
        "updated_at": now,
    }
    if rkey:
        existing = await get_goal(client, rkey)
        record["created_at"] = existing.get("created_at", now) if existing else now
        result = client.client.com.atproto.repo.put_record(
            data={
                "repo": client.client.me.did,
                "collection": GOAL_COLLECTION,
                "rkey": rkey,
                "record": record,
            }
        )
    else:
        record["created_at"] = now
        result = client.client.com.atproto.repo.create_record(
            data={
                "repo": client.client.me.did,
                "collection": GOAL_COLLECTION,
                "record": record,
            }
        )
    return result.uri
