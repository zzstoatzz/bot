"""Full personality revisions on Phi's PDS; newest TID is the active version."""

from datetime import UTC, datetime

from atproto_client.models.utils import get_model_as_dict

from bot.core.atproto_client import BotClient

COLLECTION = "io.zzstoatzz.phi.personality"
MAX_CHARS = 6000


async def read_personality(client: BotClient, fallback: str) -> str:
    """Read once per run. The repository file seeds an empty collection only.

    Errors propagate: a failed read must not silently restore an old personality.
    The run's instruction memo keeps this version fixed through its tool loop.
    """
    await client.authenticate()
    assert client.client.me is not None
    result = client.client.com.atproto.repo.list_records(
        params={
            "repo": client.client.me.did,
            "collection": COLLECTION,
            "limit": 1,
            "reverse": True,
        }
    )
    if not result.records:
        return fallback
    value = get_model_as_dict(result.records[0].value)
    text = value.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_CHARS:
        raise ValueError("The latest personality revision has invalid text")
    return text


async def write_personality(client: BotClient, text: str, reason: str) -> str:
    """Append a complete replacement; previous revisions are never overwritten."""
    if not text.strip() or len(text) > MAX_CHARS:
        raise ValueError(f"Personality must contain 1–{MAX_CHARS} characters")
    if not reason.strip() or len(reason) > 1000:
        raise ValueError("Give a reason of 1–1000 characters")
    await client.authenticate()
    assert client.client.me is not None
    result = client.client.com.atproto.repo.create_record(
        data={
            "repo": client.client.me.did,
            "collection": COLLECTION,
            "record": {
                "$type": COLLECTION,
                "text": text,
                "reason": reason,
                "createdAt": datetime.now(UTC).isoformat(),
            },
        }
    )
    return result.uri
