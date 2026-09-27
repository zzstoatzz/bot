from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy

from bot.config import settings

_client: AsyncTypeSafeClient | None = None


def get_client() -> AsyncTypeSafeClient:
    global _client
    if _client is None:
        if not settings.typesafe_api_key:
            raise RuntimeError("TypeSafe is not configured")
        _client = AsyncTypeSafeClient(
            api_key=settings.typesafe_api_key.get_secret_value(),
            model=settings.typesafe_model,
            base_url=settings.typesafe_base_url,
            timeout=settings.typesafe_timeout,
            retry=RetryPolicy(max_retries=0),
        )
    client = _client
    assert client is not None
    return client


async def close_client() -> None:
    global _client
    client, _client = _client, None
    if client is not None:
        await client.aclose()
