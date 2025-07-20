from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from bot.config import settings
from bot.core.atproto_client import bot_client
from bot.services.notification_poller import NotificationPoller
from bot.status import bot_status
from datetime import datetime


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


@app.get("/status", response_class=HTMLResponse)
async def status_page():
    """Render a simple status page"""
    # Format last activity times
    last_mention = "Never"
    if bot_status.last_mention_time:
        delta = (datetime.now() - bot_status.last_mention_time).total_seconds()
        if delta < 60:
            last_mention = f"{int(delta)}s ago"
        elif delta < 3600:
            last_mention = f"{int(delta/60)}m ago"
        else:
            last_mention = f"{int(delta/3600)}h ago"
    
    last_response = "Never"
    if bot_status.last_response_time:
        delta = (datetime.now() - bot_status.last_response_time).total_seconds()
        if delta < 60:
            last_response = f"{int(delta)}s ago"
        elif delta < 3600:
            last_response = f"{int(delta/60)}m ago"
        else:
            last_response = f"{int(delta/3600)}h ago"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{settings.bot_name} Status</title>
        <meta http-equiv="refresh" content="10">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0;
                padding: 20px;
                background: #0a0a0a;
                color: #e0e0e0;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
            }}
            h1 {{
                color: #00a8ff;
                margin-bottom: 30px;
            }}
            .status-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}
            .status-card {{
                background: #1a1a1a;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 20px;
            }}
            .status-card h3 {{
                margin: 0 0 15px 0;
                color: #00a8ff;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .status-value {{
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 5px;
            }}
            .status-label {{
                font-size: 12px;
                color: #888;
            }}
            .status-indicator {{
                display: inline-block;
                width: 10px;
                height: 10px;
                border-radius: 50%;
                margin-right: 8px;
            }}
            .status-active {{
                background: #4caf50;
            }}
            .status-inactive {{
                background: #f44336;
            }}
            .footer {{
                text-align: center;
                color: #666;
                font-size: 12px;
                margin-top: 40px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 {settings.bot_name} Status</h1>
            
            <div class="status-grid">
                <div class="status-card">
                    <h3>Bot Status</h3>
                    <div class="status-value">
                        <span class="status-indicator {'status-active' if bot_status.polling_active else 'status-inactive'}"></span>
                        {'Active' if bot_status.polling_active else 'Inactive'}
                    </div>
                    <div class="status-label">@{settings.bluesky_handle}</div>
                </div>
                
                <div class="status-card">
                    <h3>Uptime</h3>
                    <div class="status-value">{bot_status.uptime_str}</div>
                    <div class="status-label">Since startup</div>
                </div>
                
                <div class="status-card">
                    <h3>Activity</h3>
                    <div class="status-value">{bot_status.mentions_received}</div>
                    <div class="status-label">Mentions received</div>
                    <div style="margin-top: 10px;">
                        <div class="status-value">{bot_status.responses_sent}</div>
                        <div class="status-label">Responses sent</div>
                    </div>
                </div>
                
                <div class="status-card">
                    <h3>Response Mode</h3>
                    <div class="status-value">
                        {'AI Enabled' if bot_status.ai_enabled else 'Placeholder'}
                    </div>
                    <div class="status-label">
                        {'Using Anthropic Claude' if bot_status.ai_enabled else 'Random responses'}
                    </div>
                </div>
                
                <div class="status-card">
                    <h3>Last Activity</h3>
                    <div style="margin-bottom: 10px;">
                        <div class="status-label">Last mention</div>
                        <div>{last_mention}</div>
                    </div>
                    <div>
                        <div class="status-label">Last response</div>
                        <div>{last_response}</div>
                    </div>
                </div>
                
                <div class="status-card">
                    <h3>Health</h3>
                    <div class="status-value">{bot_status.errors}</div>
                    <div class="status-label">Errors encountered</div>
                </div>
            </div>
            
            <div class="footer">
                <p>Auto-refreshes every 10 seconds</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html