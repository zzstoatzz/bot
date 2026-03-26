"""FastAPI application for phi."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime

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


NAV_HTML = '<nav><a href="/">phi</a><a href="/status">status</a><a href="/memory">memory</a></nav>'

BASE_STYLE = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
        background: #0d1117; color: #c9d1d9;
    }
    nav {
        padding: 12px 20px;
        border-bottom: 1px solid #30363d;
        background: #0d1117;
    }
    nav a {
        color: #8b949e; text-decoration: none; margin-right: 20px;
        font-size: 13px; letter-spacing: 0.5px;
    }
    nav a:hover { color: #c9d1d9; }
    .container { max-width: 720px; margin: 0 auto; padding: 40px 20px; }
    a { color: #58a6ff; text-decoration: none; }
    a:hover { text-decoration: underline; }
"""


@app.get("/", response_class=HTMLResponse)
async def root():
    """Landing page."""
    status = "online" if bot_status.polling_active else "offline"
    status_color = "#2ea043" if bot_status.polling_active else "#da3633"
    return f"""<!DOCTYPE html>
<html><head><title>phi</title><style>{BASE_STYLE}
    h1 {{ font-size: 24px; font-weight: 300; margin-bottom: 8px; }}
    .subtitle {{ color: #8b949e; font-size: 13px; margin-bottom: 32px; }}
    .status-dot {{
        display: inline-block; width: 8px; height: 8px;
        border-radius: 50%; margin-right: 6px;
    }}
    .links {{ margin-top: 24px; }}
    .links a {{
        display: inline-block; color: #8b949e; margin-right: 20px;
        font-size: 13px; padding: 6px 0;
    }}
    .links a:hover {{ color: #c9d1d9; text-decoration: none; }}
</style></head>
<body>
    {NAV_HTML}
    <div class="container">
        <h1>phi</h1>
        <div class="subtitle">
            <span class="status-dot" style="background:{status_color}"></span>{status}
            &middot; <a href="https://bsky.app/profile/{settings.bluesky_handle}">@{settings.bluesky_handle}</a>
        </div>
        <p style="color:#8b949e;font-size:13px;line-height:1.6;max-width:480px">
            bluesky bot with mcp tools and episodic memory.
            learns from conversations, remembers across sessions.
        </p>
        <div class="links">
            <a href="/status">status</a>
            <a href="/memory">memory graph</a>
            <a href="/health">health</a>
            <a href="/docs">api docs</a>
        </div>
    </div>
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
    indicator = f'<span style="color:{"#2ea043" if active else "#da3633"}">{"active" if active else "inactive"}</span>'

    rows = [
        ("status", indicator),
        ("handle", f"@{settings.bluesky_handle}"),
        ("uptime", bot_status.uptime_str),
        ("mentions", str(bot_status.mentions_received)),
        ("responses", str(bot_status.responses_sent)),
        ("last mention", format_time_ago(bot_status.last_mention_time)),
        ("last response", format_time_ago(bot_status.last_response_time)),
        ("errors", str(bot_status.errors)),
    ]
    metrics_html = "\n".join(
        f'<tr><td style="color:#8b949e;padding:6px 16px 6px 0">{k}</td><td>{v}</td></tr>'
        for k, v in rows
    )

    return f"""<!DOCTYPE html>
<html><head><title>phi &middot; status</title><style>{BASE_STYLE}
    h1 {{ font-size: 18px; font-weight: 400; margin-bottom: 24px; }}
    table {{ font-size: 13px; border-collapse: collapse; }}
</style></head>
<body>
    {NAV_HTML}
    <div class="container">
        <h1>status</h1>
        <table>{metrics_html}</table>
    </div>
</body></html>"""


_graph_cache: dict[str, object] = {"data": None, "expires": 0.0}
_GRAPH_CACHE_TTL = 60  # seconds


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
<html><head><title>phi &middot; memory</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>{BASE_STYLE}
    body {{ overflow: hidden; }}
    nav {{ position: fixed; top: 0; left: 0; right: 0; z-index: 10; }}
    #graph {{ width: 100vw; height: 100vh; }}
    .tooltip {{
        position: absolute; padding: 6px 10px;
        background: #161b22; border: 1px solid #30363d;
        border-radius: 4px; font-size: 12px;
        pointer-events: none; opacity: 0;
        color: #c9d1d9; max-width: 280px;
    }}
    .legend {{
        position: fixed; bottom: 16px; left: 16px;
        background: #161b22; border: 1px solid #30363d;
        border-radius: 4px; padding: 10px 14px; font-size: 11px;
    }}
    .legend-item {{ display: flex; align-items: center; margin: 3px 0; }}
    .legend-dot {{
        width: 8px; height: 8px; border-radius: 50%;
        margin-right: 8px; flex-shrink: 0;
    }}
    #loading {{
        position: fixed; top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        color: #8b949e; font-size: 13px;
    }}
</style></head>
<body>
    {NAV_HTML}
    <div id="loading">loading...</div>
    <div id="graph"></div>
    <div class="tooltip" id="tooltip"></div>
    <div class="legend">
        <div class="legend-item"><div class="legend-dot" style="background:#58a6ff"></div>phi</div>
        <div class="legend-item"><div class="legend-dot" style="background:#2ea043"></div>user</div>
        <div class="legend-item"><div class="legend-dot" style="background:#8b949e"></div>tag</div>
        <div class="legend-item"><div class="legend-dot" style="background:#a371f7"></div>episodic</div>
    </div>
    <script>
    const colors = {{ phi: '#58a6ff', user: '#2ea043', tag: '#8b949e', episodic: '#a371f7' }};
    const radii = {{ phi: 14, user: 9, tag: 5, episodic: 7 }};

    fetch('/api/memory/graph')
        .then(r => r.json())
        .then(data => {{
            document.getElementById('loading').remove();
            if (!data.nodes.length) return;

            const width = window.innerWidth;
            const height = window.innerHeight;
            const tooltip = d3.select('#tooltip');

            const svg = d3.select('#graph')
                .append('svg')
                .attr('width', width)
                .attr('height', height);

            const g = svg.append('g');

            svg.call(d3.zoom()
                .scaleExtent([0.2, 5])
                .on('zoom', e => g.attr('transform', e.transform)));

            const simulation = d3.forceSimulation(data.nodes)
                .force('link', d3.forceLink(data.edges).id(d => d.id).distance(80))
                .force('charge', d3.forceManyBody().strength(-200))
                .force('center', d3.forceCenter(width / 2, height / 2))
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
                .attr('fill', d => colors[d.type])
                .attr('stroke', '#0d1117')
                .attr('stroke-width', 1.5)
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
                .data(data.nodes.filter(d => d.type === 'phi' || d.type === 'user'))
                .join('text')
                .text(d => d.label)
                .attr('font-size', d => d.type === 'phi' ? 13 : 10)
                .attr('font-family', "'SF Mono', 'Cascadia Code', 'Fira Code', monospace")
                .attr('fill', '#8b949e')
                .attr('text-anchor', 'middle')
                .attr('dy', d => radii[d.type] + 14);

            simulation.on('tick', () => {{
                link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
                node.attr('cx', d => d.x).attr('cy', d => d.y);
                label.attr('x', d => d.x).attr('y', d => d.y);
            }});
        }})
        .catch(err => {{
            document.getElementById('loading').textContent = 'failed to load: ' + err;
        }});
    </script>
</body></html>"""
