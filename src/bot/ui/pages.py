"""HTML page templates for phi's web UI."""

VIEWPORT_META = '<meta name="viewport" content="width=device-width, initial-scale=1">'

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


def home_page(
    *,
    handle: str,
    status: str,
    status_color: str,
    uptime: str,
    mentions: int,
    responses: int,
) -> str:
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
    .card-header {{
        display: flex; align-items: center; gap: 6px;
        margin-bottom: 6px;
    }}
    .card-icon {{ flex-shrink: 0; }}
    .card-icon svg {{ display: block; }}
    .card-type {{
        font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
        font-weight: 500;
    }}
    .type-post {{ color: #58a6ff; }}
    .type-note {{ color: #a371f7; }}
    .type-url {{ color: #2ea043; }}
    .card-title {{ font-size: 14px; font-weight: 500; color: #c9d1d9; margin-bottom: 4px; }}
    .card-text {{ font-size: 14px; line-height: 1.5; margin-bottom: 8px; word-break: break-word; }}
    .card-text a {{ color: #58a6ff; text-decoration: none; }}
    .card-text a:hover {{ text-decoration: underline; }}
    .card-domain {{
        font-size: 12px; color: #8b949e; margin-bottom: 6px;
        display: flex; align-items: center; gap: 4px;
    }}
    .card-domain a {{ color: #8b949e; }}
    .card-domain a:hover {{ color: #c9d1d9; }}
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
                <a href="https://bsky.app/profile/{handle}">@{handle}</a>
            </div>
        </div>
        <p class="desc">
            bluesky bot with episodic memory and mcp tools.
            learns from conversations, remembers across sessions.
        </p>
        <div class="stats">
            <div><span class="stat-val">{uptime}</span>uptime</div>
            <div><span class="stat-val">{mentions}</span>mentions</div>
            <div><span class="stat-val">{responses}</span>responses</div>
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
    function linkify(text) {{
        return text.replace(/(https?:\\/\\/[^\\s<>"{{}}|\\\\^`\\[\\]]+)/g,
            '<a href="$1" target="_blank" rel="noopener">$1</a>');
    }}
    function getDomain(url) {{
        try {{ return new URL(url).hostname.replace(/^www\\./, ''); }}
        catch {{ return ''; }}
    }}
    const icons = {{
        post: `<svg width="14" height="14" viewBox="0 0 600 530" fill="#58a6ff">
            <path d="M135.72 44.03C202.22 93.87 284.5 149.63 300 163.14c15.5-13.51 97.78-69.27 164.28-119.11C528.23-2.96 600-21.03 600 66.94c0 17.58-10.06 147.67-15.96 168.71-20.48 73.22-95.26 91.94-163.03 80.59 118.4 20.18 148.52 86.98 83.52 153.79C395 580.88 300 538.04 300 538.04s-95-42.84-204.53 67.97C30.47 418.22 60.59 351.42 178.99 331.24c-67.77 11.35-142.55-7.37-163.03-80.59C10.06 229.61 0 99.52 0 81.94c0-87.97 71.77-69.9 135.72-37.91z"/>
        </svg>`,
        note: `<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="#a371f7" stroke-width="1.5">
            <path d="M8 1l2.12 4.3 4.74.69-3.43 3.34.81 4.72L8 11.77l-4.24 2.23.81-4.72L1.14 5.94l4.74-.69L8 1z"/>
        </svg>`,
        url: `<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="#2ea043" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M6.75 9.25a3.5 3.5 0 005-.5M9.25 6.75a3.5 3.5 0 00-5 .5M10 3.5l1-1a2.12 2.12 0 013 3l-1 1M6 12.5l-1 1a2.12 2.12 0 01-3-3l1-1"/>
        </svg>`
    }};
    const labels = {{
        post: 'bluesky',
        note: 'semble note',
        url: 'semble bookmark'
    }};
    function viewUrl(item) {{
        if (item.url) return item.url;
        if (item.uri && item.uri.startsWith('at://')) return 'https://pds.ls/' + item.uri;
        return '';
    }}
    fetch('/api/activity')
        .then(r => r.json())
        .then(items => {{
            const el = document.getElementById('feed');
            document.getElementById('feed-loading').remove();
            if (!items.length) {{ el.textContent = 'no recent activity'; return; }}
            el.innerHTML = items.map(i => {{
                const domain = i.url ? getDomain(i.url) : '';
                const domainHtml = (i.type === 'url' && domain)
                    ? `<div class="card-domain"><a href="${{i.url}}" target="_blank" rel="noopener">${{domain}}</a></div>`
                    : '';
                const titleHtml = i.title ? `<div class="card-title">${{i.title}}</div>` : '';
                const link = viewUrl(i);
                return `
                <div class="card card-${{i.type}}">
                    <div class="card-header">
                        <span class="card-icon">${{icons[i.type] || ''}}</span>
                        <div class="card-type type-${{i.type}}">${{labels[i.type] || i.type}}</div>
                    </div>
                    ${{domainHtml}}
                    ${{titleHtml}}
                    <div class="card-text">${{linkify(truncate(i.text || '', 300))}}</div>
                    <div class="card-meta">
                        ${{timeAgo(i.time)}}
                        ${{link ? ` &middot; <a href="${{link}}" target="_blank" rel="noopener">view</a>` : ''}}
                    </div>
                </div>`;
            }}).join('');
        }})
        .catch(() => {{
            document.getElementById('feed-loading').textContent = 'failed to load activity';
        }});
    </script>
</body></html>"""


def status_page(*, cards_html: str) -> str:
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


def memory_page(*, handle: str) -> str:
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
        <div class="legend-title">social graph &middot; positioned by semantic similarity</div>
        <div class="legend-item"><div class="legend-dot" style="background:#58a6ff"></div><span class="legend-label">phi (self)</span></div>
        <div class="legend-item"><div class="legend-dot" style="background:#2ea043"></div><span class="legend-label">identities phi knows</span></div>
    </div>
    <script>
    const colors = {{ phi: '#58a6ff', user: '#2ea043' }};
    const radii = {{ phi: 14, user: 9 }};

    async function fetchAvatars(nodes) {{
        const identities = nodes
            .filter(d => d.type === 'phi' || d.type === 'user')
            .map(d => {{
                const h = d.label.replace(/^@/, '');
                return d.type === 'phi' ? '{handle}' : h;
            }})
            .filter(h => h && !h.includes('example'));
        if (!identities.length) return {{}};
        const map = {{}};
        for (let i = 0; i < identities.length; i += 25) {{
            const chunk = identities.slice(i, i + 25);
            const params = chunk.map(h => 'actors=' + encodeURIComponent(h)).join('&');
            try {{
                const res = await fetch('https://typeahead.waow.tech/xrpc/app.bsky.actor.getProfiles?' + params);
                if (!res.ok) continue;
                const data = await res.json();
                for (const p of data.profiles || []) {{
                    if (p.avatar) map[p.handle] = p.avatar;
                }}
            }} catch {{ /* skip failed batch */ }}
        }}
        return map;
    }}

    fetch('/api/memory/graph')
        .then(r => r.json())
        .then(async data => {{
            document.getElementById('loading').remove();
            if (!data.nodes.length) return;

            const avatarMap = await fetchAvatars(data.nodes);
            data.nodes.forEach(d => {{
                if (d.type === 'phi') d.avatar = avatarMap['{handle}'];
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

            data.nodes.filter(d => d.avatar).forEach((d, i) => {{
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
                        const base = d.type === 'phi' ? 13 : 10;
                        return base / Math.max(currentZoom.k, 0.5);
                    }});
                }}));

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
                .data(data.nodes)
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
