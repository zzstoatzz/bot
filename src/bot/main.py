import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.core.profile_manager import ProfileManager
from bot.services.notification_poller import NotificationPoller
from bot.status import bot_status
from bot.templates import STATUS_PAGE_TEMPLATE

logger = logging.getLogger("bot.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🤖 Starting bot as @{settings.bluesky_handle}")

    # Authenticate first
    await bot_client.authenticate()
    
    # Set up profile manager and mark as online
    profile_manager = ProfileManager(bot_client.client)
    await profile_manager.set_online_status(True)
    
    poller = NotificationPoller(bot_client)
    await poller.start()

    logger.info("✅ Bot is online! Listening for mentions...")

    yield

    logger.info("🛑 Shutting down bot...")
    await poller.stop()
    
    # Mark as offline before shutdown
    await profile_manager.set_online_status(False)
    
    logger.info("👋 Bot shutdown complete")
    # The task is already cancelled by poller.stop(), no need to await it again


app = FastAPI(
    title=settings.bot_name,
    description="A Bluesky bot powered by LLMs",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    return {
        "name": settings.bot_name,
        "status": "running",
        "handle": settings.bluesky_handle,
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/status", response_class=HTMLResponse)
async def status_page():
    """Render a simple status page"""

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

    return STATUS_PAGE_TEMPLATE.format(
        bot_name=settings.bot_name,
        status_class="status-active"
        if bot_status.polling_active
        else "status-inactive",
        status_text="Active" if bot_status.polling_active else "Inactive",
        handle=settings.bluesky_handle,
        uptime=bot_status.uptime_str,
        mentions_received=bot_status.mentions_received,
        responses_sent=bot_status.responses_sent,
        ai_mode="AI Enabled" if bot_status.ai_enabled else "Placeholder",
        ai_description="Using Anthropic Claude"
        if bot_status.ai_enabled
        else "Random responses",
        last_mention=format_time_ago(bot_status.last_mention_time),
        last_response=format_time_ago(bot_status.last_response_time),
        errors=bot_status.errors,
    )
