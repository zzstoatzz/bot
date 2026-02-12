"""Logging configuration for the bot."""

import logging

from logfire.integrations.logging import LogfireLoggingHandler


def setup_logging(debug: bool = False) -> None:
    """Bridge stdlib logging into logfire's OTel pipeline."""
    level = logging.DEBUG if debug else logging.INFO

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    root_logger.addHandler(LogfireLoggingHandler(level=level))

    # uvicorn installs its own handlers — clear them so logs propagate to root.
    # called again in lifespan since uvicorn re-installs handlers on startup.
    _clear_uvicorn_handlers()

    # httpx/httpcore log full request tuples — logfire traces HTTP as spans already
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # SDK debug loggers dump full request bodies (embeddings, prompts)
    for name in ["anthropic._base_client", "openai._base_client", "turbopuffer._base_client"]:
        logging.getLogger(name).setLevel(logging.WARNING)

    # MCP protocol chatter (session init, tool listings, SSE messages)
    for name in ["mcp", "mcp.client", "mcp.client.session", "mcp.client.streamable_http", "pydantic_ai.mcp"]:
        logging.getLogger(name).setLevel(logging.WARNING)


def _clear_uvicorn_handlers() -> None:
    """Strip uvicorn's handlers so its logs flow through the root logger."""
    for name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True
