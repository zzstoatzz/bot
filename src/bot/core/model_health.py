"""Whether phi's models can answer at all.

A provider account out of credits, or a key it refuses, fails every request
until the operator acts. Retries and restarts change nothing, and the poller
keeps ticking, so the liveness check stays green while every run fails. Each
model phi builds goes through `checked()`: a request refused for one of those
reasons marks the model unavailable, and its next answered request clears it.
`/health` reports the list.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelAuthenticationError, ModelQuotaExceededError
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import (
    Model,
    ModelRequestParameters,
    StreamedResponse,
    infer_model,
)
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings

logger = logging.getLogger("bot.model_health")

# Failures only the operator can end: an account that cannot pay for the
# request, or credentials the provider refuses.
ACCOUNT_FAILURES = (ModelQuotaExceededError, ModelAuthenticationError)


@dataclass(frozen=True)
class Unavailable:
    model: str
    reason: str
    since: datetime

    def as_dict(self) -> dict[str, str]:
        return {
            "model": self.model,
            "reason": self.reason,
            "since": self.since.isoformat(),
        }


_unavailable: dict[str, Unavailable] = {}


def _reason(error: Exception) -> str:
    kind = (
        "out of credits or quota"
        if isinstance(error, ModelQuotaExceededError)
        else "credentials refused"
    )
    status = getattr(error, "status_code", None)
    return f"{kind} ({status})" if status else kind


def record_failure(model: str, error: Exception) -> None:
    if model not in _unavailable:
        _unavailable[model] = Unavailable(model, _reason(error), datetime.now(UTC))
        logger.error(f"model {model} unavailable: {_reason(error)}: {error}")


def record_answer(model: str) -> None:
    if _unavailable.pop(model, None) is not None:
        logger.info(f"model {model} answering again")


def unavailable() -> list[Unavailable]:
    return list(_unavailable.values())


def reset() -> None:
    _unavailable.clear()


class AccountCheckedModel(WrapperModel):
    """Records whether the wrapped model's provider accepted each request."""

    def __init__(self, wrapped: Model | str):
        super().__init__(infer_model(wrapped))

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        try:
            response = await super().request(
                messages, model_settings, model_request_parameters
            )
        except ACCOUNT_FAILURES as e:
            record_failure(self.wrapped.model_name, e)
            raise
        record_answer(self.wrapped.model_name)
        return response

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: RunContext[Any] | None = None,
    ) -> AsyncGenerator[StreamedResponse]:
        try:
            async with super().request_stream(
                messages, model_settings, model_request_parameters, run_context
            ) as stream:
                yield stream
        except ACCOUNT_FAILURES as e:
            record_failure(self.wrapped.model_name, e)
            raise
        record_answer(self.wrapped.model_name)


def checked(model: Model | str) -> Model:
    """`model`, reporting account failures to `/health`."""
    return AccountCheckedModel(model)
