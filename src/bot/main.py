"""FastAPI application for phi.

Serves:
- API endpoints under /api/* and /health (consumed by both the SvelteKit
  frontend and external automations)
- The SvelteKit static build mounted at / as a SPA (with fallback to
  index.html so client-side routes work). The frontend lives in
  bot/web/, builds to bot/web/build/, and is copied into the docker
  image at /app/web/.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

import logfire
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.core.discovery_pool import get_filtered_pool
from bot.core.profile_manager import ProfileManager
from bot.logging_config import _clear_uvicorn_handlers
from bot.memory import NamespaceMemory
from bot.services.notification_poller import NotificationPoller
from bot.status import bot_status
from bot.ui import activity_router

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
    description="phi: a bluesky bot with episodic memory and an active attention pool",
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


@app.get("/health")
async def health():
    """Health check endpoint — also consumed by the frontend's status pill."""
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


_discovery_cache_data: list | None = None
_discovery_cache_expires: float = 0.0
_DISCOVERY_CACHE_TTL = 60  # seconds


@app.get("/api/discovery")
async def discovery():
    """Discovery pool — filtered to what phi actually sees in her prompt.

    Joins the upstream operator-likes pool (hub) with phi's per-author
    interaction state. The frontend reads this so the public page stays
    aligned with phi's view; previously it called hub directly and showed
    a different (raw) list than the one phi was reasoning over.
    """
    global _discovery_cache_data, _discovery_cache_expires
    now = time.monotonic()
    if _discovery_cache_data is not None and now < _discovery_cache_expires:
        return JSONResponse(_discovery_cache_data)

    memory: NamespaceMemory | None = None
    if settings.turbopuffer_api_key and settings.openai_api_key:
        try:
            memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)
        except Exception as e:
            logger.debug(f"discovery: memory client init failed: {e}")

    try:
        entries = await get_filtered_pool(memory)
    except Exception as e:
        logger.warning(f"discovery: get_filtered_pool failed: {e}")
        return JSONResponse([], status_code=200)

    _discovery_cache_data = entries
    _discovery_cache_expires = now + _DISCOVERY_CACHE_TTL
    return JSONResponse(entries)


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


# --- frontend mount ---
#
# bot/web/ is a sveltekit project built with adapter-static. the build
# directory is copied into /app/web/ in the docker runtime stage. in dev,
# this directory may not exist (just run `bun run dev` separately and let
# vite proxy /api/* to the python server) — we mount conditionally so dev
# of the python side doesn't fail.
#
# routing layering:
#   1. all explicit @app.get/@app.post handlers above (api, control, health)
#   2. StaticFiles mount at "/" — serves index.html for "/" and any real
#      file under /app/web/* (assets, favicon)
#   3. 404 handler — for client-side routes (/feed, /mind, etc) that have
#      no corresponding file, falls back to index.html so the svelte
#      router takes over.
#
# the previous version registered an @app.get("/{full_path:path}") catch-all
# BEFORE the mount, which intercepted every request including JS assets and
# returned index.html with text/html content-type — browsers refuse to load
# js modules served as text/html, so the SPA never booted.

WEB_DIR = Path(settings.web_build_dir)
if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    logger.info(f"frontend mounted from {WEB_DIR}")

    @app.exception_handler(404)
    async def spa_fallback(request: Request, exc):  # noqa: ARG001
        # Only fall back for browser navigation requests; api/health 404s
        # should still return JSON.
        path = request.url.path
        if path.startswith("/api/") or path == "/health":
            return JSONResponse({"error": "not found"}, status_code=404)
        return FileResponse(WEB_DIR / "index.html")
else:
    logger.warning(
        f"frontend build not found at {WEB_DIR} — only API routes will be served"
    )
