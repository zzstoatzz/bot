"""Internal helper for writing cosmik records from pipeline code.

Phi-driven cosmik writes go through the `cosmik-records` skill — phi
loads it on demand and uses pdsx for record CRUD. This module exists for
the *internal* pipeline that promotes phi's own observations to public
cards (see `agent.py:process_review`), where there's no agent run to
load a skill — we just write the record directly.
"""

from bot.core.atproto_client import bot_client


async def create_cosmik_record(collection: str, record: dict) -> str:
    """Write a cosmik record to phi's PDS. Returns the AT URI."""
    await bot_client.authenticate()
    assert bot_client.client.me is not None
    result = bot_client.client.com.atproto.repo.create_record(
        data={
            "repo": bot_client.client.me.did,
            "collection": collection,
            "record": record,
        }
    )
    return result.uri
