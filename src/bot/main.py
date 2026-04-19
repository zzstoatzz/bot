"""FastAPI application for phi."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime

import logfire
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.core.profile_manager import ProfileManager
from bot.logging_config import _clear_uvicorn_handlers
from bot.memory import NamespaceMemory
from bot.services.notification_poller import NotificationPoller
from bot.status import bot_status
from bot.ui import activity_router, home_page, memory_page, status_page

logger = logging.getLogger("bot.main")

logfire.configure(
    send_to_logfire=settings.logfire.send_to_logfire,
    environment=settings.logfire.environment,
    token=settings.logfire.write_token,
    console=logfire.ConsoleOptions(
        min_log_level="debug" if settings.debug else "info",
    ),
)

# instrument the interesting stuff — skip httpx (poll noise) since
# anthropic/openai integrations already trace their own HTTP calls.
# each call is wrapped individually so a missing dep degrades to a no-op.
for _instrument in (
    logfire.instrument_pydantic_ai,
    logfire.instrument_anthropic,
    logfire.instrument_openai,
):
    try:
        _instrument()
    except Exception as _e:
        logger.warning(f"logfire instrumentation failed ({_instrument.__name__}): {_e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    _clear_uvicorn_handlers()  # uvicorn re-installs handlers on startup
    logger.info(f"starting phi as @{settings.bluesky_handle}")

    await bot_client.authenticate()

    # Set online status
    profile_manager = ProfileManager(bot_client.client)
    await profile_manager.set_online_status(True)
    app.state.profile_manager = profile_manager

    # Start notification polling
    poller = NotificationPoller(bot_client)
    app.state.poller = poller
    await poller.start()

    logger.info("phi is online, listening for mentions")

    yield

    logger.info("shutting down phi")
    await poller.stop()

    # Set offline status
    await profile_manager.set_online_status(False)

    logger.info("phi shutdown complete")


limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(
    title=settings.bot_name,
    description="consciousness exploration bot with episodic memory",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: JSONResponse(
        status_code=429,
        content={"error": "rate limit exceeded", "detail": str(exc)},
    ),
)

try:
    logfire.instrument_fastapi(app, excluded_urls="/health")
except Exception as _e:
    logger.warning(f"logfire fastapi instrumentation failed: {_e}")

app.include_router(activity_router)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Landing page with activity feed."""
    status = "online" if bot_status.polling_active else "offline"
    status_color = "#2ea043" if bot_status.polling_active else "#da3633"
    return home_page(
        handle=settings.bluesky_handle,
        status=status,
        status_color=status_color,
        uptime=bot_status.uptime_str,
        mentions=bot_status.mentions_received,
        responses=bot_status.responses_sent,
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "polling_active": bot_status.polling_active,
        "paused": bot_status.paused,
    }


def _check_control_token(request: Request):
    """Validate bearer token for control endpoints."""
    if not settings.control_token:
        return JSONResponse({"error": "control token not configured"}, status_code=503)
    auth = request.headers.get("authorization", "")
    if auth != f"Bearer {settings.control_token}":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return None


@app.post("/api/control/pause")
async def pause(request: Request):
    """Pause notification processing. Unread notifications accumulate until resumed."""
    if err := _check_control_token(request):
        return err
    bot_status.paused = True
    logger.info("paused via API")
    if pm := getattr(app.state, "profile_manager", None):
        await pm.set_online_status(False)
    return {"paused": True}


@app.post("/api/control/resume")
async def resume(request: Request):
    """Resume notification processing. Queued notifications will be processed on next poll."""
    if err := _check_control_token(request):
        return err
    bot_status.paused = False
    logger.info("resumed via API")
    if pm := getattr(app.state, "profile_manager", None):
        await pm.set_online_status(True)
    return {"paused": False}


@app.post("/api/control/post")
async def trigger_post(request: Request, background_tasks: BackgroundTasks):
    """Trigger an original thought post immediately."""
    if err := _check_control_token(request):
        return err
    poller: NotificationPoller | None = getattr(app.state, "poller", None)
    if not poller:
        return JSONResponse({"error": "poller not available"}, status_code=503)
    background_tasks.add_task(poller.handler.original_thought)
    logger.info("original thought triggered via API")
    return {"triggered": True}


@app.post("/api/control/review")
async def trigger_review(request: Request, background_tasks: BackgroundTasks):
    """Trigger a memory review (dream/distill pass) immediately."""
    if err := _check_control_token(request):
        return err
    poller: NotificationPoller | None = getattr(app.state, "poller", None)
    if not poller:
        return JSONResponse({"error": "poller not available"}, status_code=503)
    background_tasks.add_task(poller.handler.review_memories)
    logger.info("memory review triggered via API")
    return {"triggered": True}


@app.get("/status", response_class=HTMLResponse)
async def status_page_route():
    """Status page."""

    def format_time_ago(timestamp):
        if not timestamp:
            return "never"
        delta = (datetime.now() - timestamp).total_seconds()
        if delta < 60:
            return f"{int(delta)}s ago"
        elif delta < 3600:
            return f"{int(delta / 60)}m ago"
        else:
            return f"{int(delta / 3600)}h ago"

    active = bot_status.polling_active
    status_text = "online" if active else "offline"
    status_color = "#2ea043" if active else "#da3633"
    error_color = "#da3633" if bot_status.errors > 0 else "#c9d1d9"

    metrics = [
        ("uptime", bot_status.uptime_str, "#58a6ff"),
        ("status", status_text, status_color),
        ("mentions", str(bot_status.mentions_received), "#c9d1d9"),
        ("responses", str(bot_status.responses_sent), "#c9d1d9"),
        ("last mention", format_time_ago(bot_status.last_mention_time), "#8b949e"),
        ("last response", format_time_ago(bot_status.last_response_time), "#8b949e"),
        ("errors", str(bot_status.errors), error_color),
        ("handle", f"@{settings.bluesky_handle}", "#58a6ff"),
    ]
    cards_html = "\n".join(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value" style="color:{color}">{value}</div></div>'
        for label, value, color in metrics
    )

    return status_page(cards_html=cards_html)


_graph_cache_data: dict | None = None
_graph_cache_expires: float = 0.0
_GRAPH_CACHE_TTL = 60  # seconds


@app.get("/api/memory/graph")
@limiter.limit("10/minute")
async def memory_graph_data(request: Request):
    """Return graph nodes and edges as JSON."""
    global _graph_cache_data, _graph_cache_expires
    now = time.monotonic()
    if _graph_cache_data is not None and now < _graph_cache_expires:
        return JSONResponse(_graph_cache_data)

    try:
        memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, memory.get_graph_data)
        _graph_cache_data = data
        _graph_cache_expires = now + _GRAPH_CACHE_TTL
        return JSONResponse(data)
    except Exception as e:
        logger.warning(f"memory graph failed: {e}")
        return JSONResponse(
            {"nodes": [], "edges": [], "error": str(e)}, status_code=500
        )


@app.get("/memory", response_class=HTMLResponse)
async def memory_page_route():
    """Interactive memory graph visualization."""
    return memory_page(handle=settings.bluesky_handle)
