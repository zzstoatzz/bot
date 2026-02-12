"""FastAPI application for phi."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

import logfire
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.core.profile_manager import ProfileManager
from bot.logging_config import _clear_uvicorn_handlers
from bot.services.notification_poller import NotificationPoller
from bot.status import bot_status

logger = logging.getLogger("bot.main")

logfire.configure(
    send_to_logfire=settings.logfire.send_to_logfire,
    environment=settings.logfire.environment,
    token=settings.logfire.token,
    console=logfire.ConsoleOptions(
        min_log_level="debug" if settings.debug else "info",
    ),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    _clear_uvicorn_handlers()  # uvicorn re-installs handlers on startup
    logger.info(f"starting phi as @{settings.bluesky_handle}")

    await bot_client.authenticate()

    # Set online status
    profile_manager = ProfileManager(bot_client.client)
    await profile_manager.set_online_status(True)

    # Start notification polling
    poller = NotificationPoller(bot_client)
    await poller.start()

    logger.info("phi is online, listening for mentions")

    yield

    logger.info("shutting down phi")
    await poller.stop()

    # Set offline status
    await profile_manager.set_online_status(False)

    logger.info("phi shutdown complete")


app = FastAPI(
    title=settings.bot_name,
    description="consciousness exploration bot with episodic memory",
    lifespan=lifespan,
)

logfire.instrument_fastapi(app)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.bot_name,
        "status": "running",
        "handle": settings.bluesky_handle,
        "architecture": "mcp + episodic memory",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "polling_active": bot_status.polling_active}


@app.get("/status", response_class=HTMLResponse)
async def status_page():
    """Simple status page."""

    def format_time_ago(timestamp):
        if not timestamp:
            return "Never"
        delta = (datetime.now() - timestamp).total_seconds()
        if delta < 60:
            return f"{int(delta)}s ago"
        elif delta < 3600:
            return f"{int(delta / 60)}m ago"
        else:
            return f"{int(delta / 3600)}h ago"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{settings.bot_name} Status</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                max-width: 800px;
                margin: 40px auto;
                padding: 20px;
                background: #0d1117;
                color: #c9d1d9;
            }}
            .status {{
                padding: 20px;
                background: #161b22;
                border-radius: 6px;
                border: 1px solid #30363d;
                margin-bottom: 20px;
            }}
            .active {{ border-left: 4px solid #2ea043; }}
            .inactive {{ border-left: 4px solid #da3633; }}
            h1 {{ margin-top: 0; }}
            .metric {{ margin: 10px 0; }}
            .label {{ color: #8b949e; }}
        </style>
    </head>
    <body>
        <h1>{settings.bot_name}</h1>
        <div class="status {'active' if bot_status.polling_active else 'inactive'}">
            <div class="metric">
                <span class="label">Status:</span>
                <strong>{'Active' if bot_status.polling_active else 'Inactive'}</strong>
            </div>
            <div class="metric">
                <span class="label">Handle:</span> @{settings.bluesky_handle}
            </div>
            <div class="metric">
                <span class="label">Uptime:</span> {bot_status.uptime_str}
            </div>
            <div class="metric">
                <span class="label">Mentions received:</span> {bot_status.mentions_received}
            </div>
            <div class="metric">
                <span class="label">Responses sent:</span> {bot_status.responses_sent}
            </div>
            <div class="metric">
                <span class="label">Last mention:</span> {format_time_ago(bot_status.last_mention_time)}
            </div>
            <div class="metric">
                <span class="label">Last response:</span> {format_time_ago(bot_status.last_response_time)}
            </div>
            <div class="metric">
                <span class="label">Errors:</span> {bot_status.errors}
            </div>
            <div class="metric">
                <span class="label">Architecture:</span> MCP-enabled with episodic memory (TurboPuffer)
            </div>
        </div>
    </body>
    </html>
    """
    return html
