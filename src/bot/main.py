from contextlib import asynccontextmanager

from fastapi import FastAPI

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.services.notification_poller import NotificationPoller


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🤖 Starting bot as @{settings.bluesky_handle}")
    
    poller = NotificationPoller(bot_client)
    poller_task = await poller.start()
    
    print(f"✅ Bot is online! Listening for mentions...")
    
    yield
    
    print("🛑 Shutting down bot...")
    await poller.stop()
    print("👋 Bot shutdown complete")
    # The task is already cancelled by poller.stop(), no need to await it again


app = FastAPI(
    title=settings.bot_name,
    description="A Bluesky bot powered by LLMs",
    lifespan=lifespan
)


@app.get("/")
async def root():
    return {
        "name": settings.bot_name,
        "status": "running",
        "handle": settings.bluesky_handle
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}