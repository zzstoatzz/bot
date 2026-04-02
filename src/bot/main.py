"""FastAPI application for phi."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
import logfire
from fastapi import FastAPI, Request
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


PHI_DID = "did:plc:65sucjiel52gefhcdcypynsr"

VIEWPORT_META = '<meta name="viewport" content="width=device-width, initial-scale=1">'

# per-page favicons — thematically distinct inline SVGs
_FAVICON_HOME = (
    '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,'
    "%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22%3E"
    "%3Cpath d=%22M2 16 L8 16 L11 6 L16 26 L21 10 L24 16 L30 16%22"
    " fill=%22none%22 stroke=%2258a6ff%22 stroke-width=%222.5%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22/%3E"
    '%3C/svg%3E">'
)
_FAVICON_STATUS = (
    '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,'
    "%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22%3E"
    "%3Ccircle cx=%2216%22 cy=%2216%22 r=%2212%22 fill=%22none%22 stroke=%222ea043%22 stroke-width=%222%22/%3E"
    "%3Cline x1=%2216%22 y1=%2216%22 x2=%2216%22 y2=%228%22 stroke=%222ea043%22 stroke-width=%222.5%22 stroke-linecap=%22round%22/%3E"
    "%3Cline x1=%2216%22 y1=%2216%22 x2=%2222%22 y2=%2218%22 stroke=%222ea043%22 stroke-width=%222%22 stroke-linecap=%22round%22/%3E"
    "%3Ccircle cx=%2216%22 cy=%2216%22 r=%222%22 fill=%222ea043%22/%3E"
    '%3C/svg%3E">'
)
_FAVICON_MEMORY = (
    '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,'
    "%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22%3E"
    "%3Cline x1=%228%22 y1=%2210%22 x2=%2220%22 y2=%227%22 stroke=%2230363d%22 stroke-width=%221.5%22/%3E"
    "%3Cline x1=%228%22 y1=%2210%22 x2=%2214%22 y2=%2224%22 stroke=%2230363d%22 stroke-width=%221.5%22/%3E"
    "%3Cline x1=%2220%22 y1=%227%22 x2=%2226%22 y2=%2220%22 stroke=%2230363d%22 stroke-width=%221.5%22/%3E"
    "%3Cline x1=%2214%22 y1=%2224%22 x2=%2226%22 y2=%2220%22 stroke=%2230363d%22 stroke-width=%221.5%22/%3E"
    "%3Ccircle cx=%228%22 cy=%2210%22 r=%223.5%22 fill=%22a371f7%22/%3E"
    "%3Ccircle cx=%2220%22 cy=%227%22 r=%223%22 fill=%2258a6ff%22/%3E"
    "%3Ccircle cx=%2226%22 cy=%2220%22 r=%222.5%22 fill=%222ea043%22/%3E"
    "%3Ccircle cx=%2214%22 cy=%2224%22 r=%223%22 fill=%228b949e%22/%3E"
    '%3C/svg%3E">'
)

NAV_HTML = """<nav>
    <a href="/" class="nav-brand">phi</a>
    <div class="nav-links">
        <a href="/status">status</a>
        <a href="/memory">memory</a>
        <a href="/docs">api</a>
    </div>
</nav>"""

BASE_STYLE = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
        background: #0d1117; color: #c9d1d9; font-size: 14px;
        -webkit-font-smoothing: antialiased;
    }
    nav {
        padding: 14px 20px;
        border-bottom: 1px solid #30363d;
        background: #0d1117;
        display: flex; align-items: center; justify-content: space-between;
    }
    .nav-brand {
        color: #c9d1d9; text-decoration: none;
        font-size: 15px; font-weight: 500; letter-spacing: 0.5px;
    }
    .nav-links { display: flex; gap: 6px; }
    .nav-links a {
        color: #8b949e; text-decoration: none;
        font-size: 13px; letter-spacing: 0.3px;
        padding: 6px 12px; border-radius: 16px;
        transition: background 0.15s, color 0.15s;
    }
    .nav-links a:hover { color: #c9d1d9; background: #161b22; }
    .container { max-width: 640px; margin: 0 auto; padding: 32px 20px; }
    a { color: #58a6ff; text-decoration: none; }
    a:hover { text-decoration: underline; }
"""


@app.get("/", response_class=HTMLResponse)
async def root():
    """Landing page with activity feed."""
    status = "online" if bot_status.polling_active else "offline"
    status_color = "#2ea043" if bot_status.polling_active else "#da3633"
    return f"""<!DOCTYPE html>
<html><head><title>phi</title>{VIEWPORT_META}{_FAVICON_HOME}<style>{BASE_STYLE}
    .header {{ margin-bottom: 28px; }}
    h1 {{ font-size: 28px; font-weight: 400; margin-bottom: 6px; }}
    .subtitle {{ color: #8b949e; font-size: 14px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
    .status-dot {{
        display: inline-block; width: 8px; height: 8px;
        border-radius: 50%; flex-shrink: 0;
    }}
    .desc {{ color: #8b949e; font-size: 14px; line-height: 1.6; margin-bottom: 24px; }}
    .stats {{
        display: flex; gap: 24px; margin-bottom: 32px;
        font-size: 13px; color: #8b949e; flex-wrap: wrap;
    }}
    .stat-val {{ color: #c9d1d9; font-size: 18px; display: block; margin-bottom: 2px; }}
    .feed-title {{ font-size: 15px; color: #8b949e; margin-bottom: 16px; font-weight: 400; }}
    .feed {{ display: flex; flex-direction: column; gap: 10px; }}
    .card {{
        background: #161b22; border-radius: 8px; padding: 14px 16px;
        border-left: 3px solid #30363d;
    }}
    .card-post {{ border-left-color: #58a6ff; }}
    .card-note {{ border-left-color: #a371f7; }}
    .card-url {{ border-left-color: #2ea043; }}
    .card-type {{
        font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
        margin-bottom: 6px; font-weight: 500;
    }}
    .type-post {{ color: #58a6ff; }}
    .type-note {{ color: #a371f7; }}
    .type-url {{ color: #2ea043; }}
    .card-text {{ font-size: 14px; line-height: 1.5; margin-bottom: 8px; word-break: break-word; }}
    .card-meta {{ font-size: 12px; color: #484f58; }}
    .card-meta a {{ color: #484f58; }}
    .card-meta a:hover {{ color: #8b949e; }}
    #feed-loading {{ color: #484f58; font-size: 13px; }}
</style></head>
<body>
    {NAV_HTML}
    <div class="container">
        <div class="header">
            <h1>phi</h1>
            <div class="subtitle">
                <span class="status-dot" style="background:{status_color}"></span>
                <span>{status}</span>
                <span>&middot;</span>
                <a href="https://bsky.app/profile/{settings.bluesky_handle}">@{settings.bluesky_handle}</a>
            </div>
        </div>
        <p class="desc">
            bluesky bot with episodic memory and mcp tools.
            learns from conversations, remembers across sessions.
        </p>
        <div class="stats">
            <div><span class="stat-val">{bot_status.uptime_str}</span>uptime</div>
            <div><span class="stat-val">{bot_status.mentions_received}</span>mentions</div>
            <div><span class="stat-val">{bot_status.responses_sent}</span>responses</div>
        </div>
        <h2 class="feed-title">recent activity</h2>
        <div class="feed" id="feed">
            <div id="feed-loading">loading...</div>
        </div>
    </div>
    <script>
    function timeAgo(iso) {{
        const s = (Date.now() - new Date(iso).getTime()) / 1000;
        if (s < 60) return Math.floor(s) + 's ago';
        if (s < 3600) return Math.floor(s / 60) + 'm ago';
        if (s < 86400) return Math.floor(s / 3600) + 'h ago';
        return Math.floor(s / 86400) + 'd ago';
    }}
    function truncate(s, n) {{ return s.length > n ? s.slice(0, n) + '...' : s; }}
    fetch('/api/activity')
        .then(r => r.json())
        .then(items => {{
            const el = document.getElementById('feed');
            document.getElementById('feed-loading').remove();
            if (!items.length) {{ el.textContent = 'no recent activity'; return; }}
            el.innerHTML = items.map(i => `
                <div class="card card-${{i.type}}">
                    <div class="card-type type-${{i.type}}">${{i.type}}</div>
                    <div class="card-text">${{truncate(i.text || '', 200)}}</div>
                    <div class="card-meta">
                        ${{timeAgo(i.time)}}
                        ${{i.url ? ` &middot; <a href="${{i.url}}" target="_blank" rel="noopener">view</a>` : ''}}
                    </div>
                </div>
            `).join('');
        }})
        .catch(() => {{
            document.getElementById('feed-loading').textContent = 'failed to load activity';
        }});
    </script>
</body></html>"""


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


@app.get("/status", response_class=HTMLResponse)
async def status_page():
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

    return f"""<!DOCTYPE html>
<html><head><title>phi &middot; status</title>{VIEWPORT_META}{_FAVICON_STATUS}<style>{BASE_STYLE}
    h1 {{ font-size: 22px; font-weight: 400; margin-bottom: 24px; }}
    .grid {{
        display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
    }}
    .metric-card {{
        background: #161b22; border-radius: 8px; padding: 16px;
        border: 1px solid #21262d;
    }}
    .metric-label {{ font-size: 12px; color: #484f58; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }}
    .metric-value {{ font-size: 18px; font-weight: 400; }}
</style></head>
<body>
    {NAV_HTML}
    <div class="container">
        <h1>status</h1>
        <div class="grid">{cards_html}</div>
    </div>
</body></html>"""


_TID_CHARSET = "234567abcdefghijklmnopqrstuvwxyz"


def _tid_to_iso(tid: str) -> str:
    """Decode an AT Protocol TID (base32-sortstring) to ISO8601."""
    try:
        n = 0
        for ch in tid:
            n = n * 32 + _TID_CHARSET.index(ch)
        # 64-bit TID: bit 63=0, bits 62..10=timestamp(us), bits 9..0=clockid
        us = (n >> 10) & ((1 << 53) - 1)
        dt = datetime.fromtimestamp(us / 1_000_000)
        return dt.isoformat()
    except (ValueError, OSError):
        return ""


_activity_cache: dict[str, object] = {"data": None, "expires": 0.0}
_ACTIVITY_CACHE_TTL = 60  # seconds

_graph_cache: dict[str, object] = {"data": None, "expires": 0.0}
_GRAPH_CACHE_TTL = 60  # seconds


@app.get("/api/activity")
async def activity_feed():
    """Recent posts and cosmik cards, merged by time."""
    now = time.monotonic()
    if _activity_cache["data"] is not None and now < _activity_cache["expires"]:
        return JSONResponse(_activity_cache["data"])

    items: list[dict] = []
    async with httpx.AsyncClient(timeout=10) as client:
        posts_coro = client.get(
            "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed",
            params={"actor": PHI_DID, "filter": "posts_no_replies", "limit": 10},
        )
        cards_coro = client.get(
            "https://bsky.social/xrpc/com.atproto.repo.listRecords",
            params={"repo": PHI_DID, "collection": "network.cosmik.card", "limit": 10},
        )
        posts_resp, cards_resp = await asyncio.gather(
            posts_coro, cards_coro, return_exceptions=True
        )

    if isinstance(posts_resp, httpx.Response) and posts_resp.status_code == 200:
        for entry in posts_resp.json().get("feed", []):
            post = entry.get("post", {})
            record = post.get("record", {})
            uri = post.get("uri", "")
            # at://did/app.bsky.feed.post/rkey -> bsky.app link
            parts = uri.split("/")
            bsky_url = (
                f"https://bsky.app/profile/{PHI_DID}/post/{parts[-1]}"
                if len(parts) >= 5
                else None
            )
            items.append(
                {
                    "type": "post",
                    "text": record.get("text", ""),
                    "time": record.get("createdAt", ""),
                    "uri": uri,
                    "url": bsky_url,
                }
            )

    if isinstance(cards_resp, httpx.Response) and cards_resp.status_code == 200:
        for rec in cards_resp.json().get("records", []):
            value = rec.get("value", {})
            card_type = value.get("type", "NOTE")
            item_type = "url" if card_type == "URL" else "note"
            content = value.get("content", {})
            if item_type == "url":
                text = (
                    content.get("title", "")
                    or content.get("description", "")
                    or content.get("url", "")
                )
            else:
                text = (
                    content.get("text", "")
                    if isinstance(content, dict)
                    else str(content)
                )
            # derive time from TID rkey (base32-sortstring microseconds)
            rkey = rec.get("uri", "").rsplit("/", 1)[-1]
            card_time = _tid_to_iso(rkey)
            items.append(
                {
                    "type": item_type,
                    "text": text,
                    "time": card_time,
                    "uri": rec.get("uri", ""),
                    "url": content.get("url") if item_type == "url" else None,
                }
            )

    items.sort(key=lambda x: x.get("time", ""), reverse=True)
    _activity_cache["data"] = items
    _activity_cache["expires"] = now + _ACTIVITY_CACHE_TTL
    return JSONResponse(items)


@app.get("/api/memory/graph")
@limiter.limit("10/minute")
async def memory_graph_data(request: Request):
    """Return graph nodes and edges as JSON."""
    now = time.monotonic()
    if _graph_cache["data"] is not None and now < _graph_cache["expires"]:
        return JSONResponse(_graph_cache["data"])

    try:
        memory = NamespaceMemory(api_key=settings.turbopuffer_api_key)
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, memory.get_graph_data)
        _graph_cache["data"] = data
        _graph_cache["expires"] = now + _GRAPH_CACHE_TTL
        return JSONResponse(data)
    except Exception as e:
        logger.warning(f"memory graph failed: {e}")
        return JSONResponse(
            {"nodes": [], "edges": [], "error": str(e)}, status_code=500
        )


@app.get("/memory", response_class=HTMLResponse)
async def memory_page():
    """Interactive memory graph visualization."""
    return f"""<!DOCTYPE html>
<html><head><title>phi &middot; memory</title>{VIEWPORT_META}{_FAVICON_MEMORY}
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>{BASE_STYLE}
    body {{ overflow: hidden; }}
    nav {{ position: fixed; top: 0; left: 0; right: 0; z-index: 10; }}
    #graph {{ width: 100vw; height: 100vh; }}
    .tooltip {{
        position: absolute; padding: 8px 12px;
        background: #161b22; border: 1px solid #30363d;
        border-radius: 6px; font-size: 13px;
        pointer-events: none; opacity: 0;
        color: #c9d1d9; max-width: 280px;
    }}
    .legend {{
        position: fixed; bottom: 16px; left: 16px;
        background: #161b22; border: 1px solid #30363d;
        border-radius: 8px; padding: 14px 16px; font-size: 12px;
        max-width: 220px;
    }}
    .legend-title {{ color: #8b949e; font-size: 11px; margin-bottom: 8px; line-height: 1.4; }}
    .legend-item {{ display: flex; align-items: center; margin: 5px 0; }}
    .legend-dot {{
        width: 8px; height: 8px; border-radius: 50%;
        margin-right: 10px; flex-shrink: 0;
    }}
    .legend-label {{ color: #c9d1d9; }}
    #loading {{
        position: fixed; top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        color: #8b949e; font-size: 14px;
    }}
</style></head>
<body>
    {NAV_HTML}
    <div id="loading">loading...</div>
    <div id="graph"></div>
    <div class="tooltip" id="tooltip"></div>
    <div class="legend">
        <div class="legend-title">nodes positioned by semantic similarity</div>
        <div class="legend-item"><div class="legend-dot" style="background:#58a6ff"></div><span class="legend-label">phi (self)</span></div>
        <div class="legend-item"><div class="legend-dot" style="background:#2ea043"></div><span class="legend-label">identities phi knows</span></div>
        <div class="legend-item"><div class="legend-dot" style="background:#8b949e"></div><span class="legend-label">topics from conversations</span></div>
        <div class="legend-item"><div class="legend-dot" style="background:#a371f7"></div><span class="legend-label">memories &amp; experiences</span></div>
    </div>
    <script>
    const colors = {{ phi: '#58a6ff', user: '#2ea043', tag: '#8b949e', episodic: '#a371f7' }};
    const radii = {{ phi: 14, user: 9, tag: 5, episodic: 7 }};

    async function fetchAvatars(nodes) {{
        // collect identity handles for phi + user nodes
        const identities = nodes
            .filter(d => d.type === 'phi' || d.type === 'user')
            .map(d => {{
                const h = d.label.replace(/^@/, '');
                return d.type === 'phi' ? '{settings.bluesky_handle}' : h;
            }})
            .filter(h => h && !h.includes('example'));
        if (!identities.length) return {{}};
        const params = identities.map(h => 'actors=' + encodeURIComponent(h)).join('&');
        try {{
            const res = await fetch('https://typeahead.waow.tech/xrpc/app.bsky.actor.getProfiles?' + params);
            if (!res.ok) return {{}};
            const data = await res.json();
            const map = {{}};
            for (const p of data.profiles || []) {{
                if (p.avatar) map[p.handle] = p.avatar;
            }}
            return map;
        }} catch {{ return {{}}; }}
    }}

    fetch('/api/memory/graph')
        .then(r => r.json())
        .then(async data => {{
            document.getElementById('loading').remove();
            if (!data.nodes.length) return;

            const avatarMap = await fetchAvatars(data.nodes);
            // attach avatar URLs to nodes
            data.nodes.forEach(d => {{
                if (d.type === 'phi') d.avatar = avatarMap['{settings.bluesky_handle}'];
                else if (d.type === 'user') d.avatar = avatarMap[d.label.replace(/^@/, '')];
            }});

            const width = window.innerWidth;
            const height = window.innerHeight;
            const pad = 60;
            const tooltip = d3.select('#tooltip');

            const sx = d => d.x != null ? pad + (d.x + 1) / 2 * (width - 2 * pad) : width / 2;
            const sy = d => d.y != null ? pad + (d.y + 1) / 2 * (height - 2 * pad) : height / 2;

            data.nodes.forEach(d => {{
                d.sx = sx(d);
                d.sy = sy(d);
                d.x = d.sx;
                d.y = d.sy;
            }});

            const svg = d3.select('#graph')
                .append('svg')
                .attr('width', width)
                .attr('height', height);

            const defs = svg.append('defs');
            const g = svg.append('g');
            let currentZoom = d3.zoomIdentity;

            // create avatar patterns for nodes that have them
            data.nodes.filter(d => d.avatar).forEach((d, i) => {{
                const r = radii[d.type];
                const pid = 'avatar-' + i;
                d._patternId = pid;
                defs.append('pattern')
                    .attr('id', pid)
                    .attr('width', 1).attr('height', 1)
                    .attr('patternContentUnits', 'objectBoundingBox')
                    .append('image')
                    .attr('href', d.avatar)
                    .attr('width', 1).attr('height', 1)
                    .attr('preserveAspectRatio', 'xMidYMid slice');
            }});

            svg.call(d3.zoom()
                .scaleExtent([0.2, 5])
                .on('zoom', e => {{
                    g.attr('transform', e.transform);
                    currentZoom = e.transform;
                    label.attr('font-size', d => {{
                        const base = d.type === 'phi' ? 13 : d.type === 'user' ? 10 : 9;
                        return base / Math.max(currentZoom.k, 0.5);
                    }});
                    label.style('display', d => {{
                        if (d.type === 'phi' || d.type === 'user') return 'block';
                        return currentZoom.k >= 1.2 ? 'block' : 'none';
                    }});
                }}));

            const edgeOpacity = (source, target) => {{
                const s = typeof source === 'object' ? source.type : '';
                const t = typeof target === 'object' ? target.type : '';
                if (s === 'phi' && t === 'user') return 0.7;
                if (s === 'user' && t === 'tag') return 0.2;
                if (s === 'tag' || t === 'tag') return 0.25;
                return 0.4;
            }};

            const simulation = d3.forceSimulation(data.nodes)
                .force('link', d3.forceLink(data.edges).id(d => d.id).distance(40))
                .force('charge', d3.forceManyBody().strength(-80))
                .force('x', d3.forceX(d => d.sx).strength(0.3))
                .force('y', d3.forceY(d => d.sy).strength(0.3))
                .force('collision', d3.forceCollide().radius(d => radii[d.type] + 4));

            const link = g.append('g')
                .selectAll('line')
                .data(data.edges)
                .join('line')
                .attr('stroke', '#21262d')
                .attr('stroke-width', 1)
                .attr('stroke-opacity', 0.5);

            const node = g.append('g')
                .selectAll('circle')
                .data(data.nodes)
                .join('circle')
                .attr('r', d => radii[d.type])
                .attr('fill', d => d._patternId ? `url(#${{d._patternId}})` : colors[d.type])
                .attr('stroke', d => d._patternId ? colors[d.type] : '#0d1117')
                .attr('stroke-width', d => d._patternId ? 2 : 1.5)
                .style('cursor', 'grab')
                .call(d3.drag()
                    .on('start', (e, d) => {{
                        if (!e.active) simulation.alphaTarget(0.3).restart();
                        d.fx = d.x; d.fy = d.y;
                    }})
                    .on('drag', (e, d) => {{ d.fx = e.x; d.fy = e.y; }})
                    .on('end', (e, d) => {{
                        if (!e.active) simulation.alphaTarget(0);
                        d.fx = null; d.fy = null;
                    }}))
                .on('mouseover', (e, d) => {{
                    tooltip.style('opacity', 1)
                        .html('<strong>' + d.label + '</strong><br><span style="color:' + colors[d.type] + '">' + d.type + '</span>');
                }})
                .on('mousemove', e => {{
                    tooltip.style('left', (e.pageX + 12) + 'px')
                        .style('top', (e.pageY - 12) + 'px');
                }})
                .on('mouseout', () => tooltip.style('opacity', 0));

            const label = g.append('g')
                .selectAll('text')
                .data(data.nodes.filter(d => d.type === 'phi' || d.type === 'user' || d.type === 'episodic'))
                .join('text')
                .text(d => d.label)
                .attr('font-size', d => d.type === 'phi' ? 13 : d.type === 'user' ? 10 : 9)
                .attr('font-family', "'SF Mono', 'Cascadia Code', 'Fira Code', monospace")
                .attr('fill', d => d.type === 'episodic' ? '#a371f7' : '#8b949e')
                .attr('fill-opacity', d => d.type === 'episodic' ? 0.6 : 1)
                .attr('text-anchor', 'middle')
                .attr('dy', d => radii[d.type] + 14)
                .style('display', d => d.type === 'episodic' ? 'none' : 'block');

            simulation.on('tick', () => {{
                link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
                    .attr('stroke-opacity', d => edgeOpacity(d.source, d.target));
                node.attr('cx', d => d.x).attr('cy', d => d.y);
                label.attr('x', d => d.x).attr('y', d => d.y);
            }});
        }})
        .catch(err => {{
            document.getElementById('loading').textContent = 'failed to load: ' + err;
        }});
    </script>
</body></html>"""
