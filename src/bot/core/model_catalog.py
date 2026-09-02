"""What the configured model can hold and what it charges, from a public catalog.

No provider's API reports its models' context windows, so the answer to
"how big is phi's window" has to come from a maintained catalog. litellm
publishes one for every provider as a single JSON file; this reads it,
caches it for a day, and falls back to a bundled snapshot
(`model_catalog.json`, the entries for models phi is configured to run)
when the network is unavailable. A model the catalog does not list gets
``max_input_tokens=None`` and ``source="unknown"`` — the panel says
"unknown", never a guess.

Prices are per token in USD, as the catalog reports them.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger("bot.model_catalog")

CATALOG_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)
CATALOG_TTL_SECONDS = 24 * 60 * 60
BUNDLED_PATH = Path(__file__).with_name("model_catalog.json")

# the catalog keys models as `<name>` or `<provider>/<name>`; pydantic-ai
# specs are `<provider>:<name>`, and a few provider spellings differ
_PROVIDER_ALIASES = {
    "openai-responses": "openai",
    "openai-chat": "openai",
    "anthropic": "anthropic",
}


@dataclass(frozen=True)
class ModelLimits:
    spec: str
    provider: str
    name: str
    max_input_tokens: int | None
    max_output_tokens: int | None
    input_cost_per_token: float | None
    output_cost_per_token: float | None
    cache_read_cost_per_token: float | None
    cache_write_cost_per_token: float | None
    source: str

    def as_dict(self) -> dict[str, object]:
        return {
            "spec": self.spec,
            "provider": self.provider,
            "name": self.name,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "input_cost_per_token": self.input_cost_per_token,
            "output_cost_per_token": self.output_cost_per_token,
            "cache_read_cost_per_token": self.cache_read_cost_per_token,
            "cache_write_cost_per_token": self.cache_write_cost_per_token,
            "source": self.source,
        }


def split_model_spec(spec: str) -> tuple[str, str]:
    """``anthropic:claude-sonnet-5`` → ``("anthropic", "claude-sonnet-5")``."""
    provider, sep, name = spec.partition(":")
    if not sep:
        return "", spec
    return _PROVIDER_ALIASES.get(provider, provider), name


def _load_bundled() -> dict[str, dict]:
    try:
        doc = json.loads(BUNDLED_PATH.read_text())
    except (OSError, ValueError) as e:
        logger.warning(f"bundled model catalog unreadable: {e}")
        return {}
    return doc.get("models") or {}


class ModelCatalog:
    """The litellm catalog with a one-day memory and a bundled fallback."""

    def __init__(self) -> None:
        self._models: dict[str, dict] = {}
        self._source = "unloaded"
        self._fetched_at = 0.0

    async def _refresh(self) -> None:
        if self._models and time.monotonic() - self._fetched_at < CATALOG_TTL_SECONDS:
            return
        try:
            async with httpx.AsyncClient(timeout=15) as http:
                resp = await http.get(CATALOG_URL)
                resp.raise_for_status()
                models = resp.json()
            self._models = {k: v for k, v in models.items() if isinstance(v, dict)}
            self._source = f"litellm@{time.strftime('%Y-%m-%d')}"
            self._fetched_at = time.monotonic()
        except Exception as e:
            if not self._models:
                self._models = _load_bundled()
                self._source = "bundled snapshot"
            logger.warning(f"model catalog fetch failed, using {self._source}: {e}")

    async def lookup(self, spec: str) -> ModelLimits:
        await self._refresh()
        provider, name = split_model_spec(spec)
        entry = None
        for key in (f"{provider}/{name}" if provider else name, name):
            if key in self._models:
                entry = self._models[key]
                break
        if entry is None:
            return ModelLimits(
                spec, provider, name, None, None, None, None, None, None, "unknown"
            )
        return ModelLimits(
            spec=spec,
            provider=provider,
            name=name,
            max_input_tokens=entry.get("max_input_tokens"),
            max_output_tokens=entry.get("max_output_tokens"),
            input_cost_per_token=entry.get("input_cost_per_token"),
            output_cost_per_token=entry.get("output_cost_per_token"),
            cache_read_cost_per_token=entry.get("cache_read_input_token_cost"),
            cache_write_cost_per_token=entry.get("cache_creation_input_token_cost"),
            source=self._source,
        )


model_catalog = ModelCatalog()


async def lookup_model_limits(spec: str) -> ModelLimits:
    return await model_catalog.lookup(spec)
