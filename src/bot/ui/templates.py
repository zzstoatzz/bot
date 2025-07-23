"""HTML templates for the bot"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.ui.context_capture import ResponseContext

CONTEXT_VISUALIZATION_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>Phi Context Visualization</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #0a0a0a; color: #e0e0e0; }}
        .response-card {{ border: 1px solid #333; margin-bottom: 20px; border-radius: 8px; overflow: hidden; background: #1a1a1a; }}
        .response-header {{ background: #2a2a2a; padding: 15px; border-bottom: 1px solid #333; }}
        .response-meta {{ font-size: 0.9em; color: #888; margin-bottom: 5px; }}
        .mention-text {{ font-weight: bold; margin-bottom: 5px; color: #e0e0e0; }}
        .generated-response {{ color: #00a8ff; font-style: italic; }}
        .components {{ padding: 15px; }}
        .component {{ margin-bottom: 15px; }}
        .component-header {{ 
            cursor: pointer; 
            padding: 10px; 
            background: #2a2a2a; 
            border: 1px solid #444; 
            border-radius: 4px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .component-header:hover {{ background: #333; }}
        .component-type {{ 
            font-size: 0.8em; 
            color: #888; 
            background: #444; 
            padding: 2px 6px; 
            border-radius: 3px; 
        }}
        .component-size {{ font-size: 0.8em; color: #888; }}
        .component-content {{ 
            display: none; 
            padding: 15px; 
            border: 1px solid #444; 
            border-top: none; 
            background: #1a1a1a; 
            white-space: pre-wrap; 
            font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; 
            font-size: 0.9em;
            max-height: 400px;
            overflow-y: auto;
        }}
        .component-content.show {{ display: block; }}
        .stats {{ display: flex; gap: 20px; margin-bottom: 10px; }}
        .stat {{ font-size: 0.9em; color: #888; }}
        h1 {{ color: #00a8ff; }}
    </style>
</head>
<body>
    <h1>🧠 Phi Context Visualization</h1>
    {responses_html}
    <script>
        function toggleComponent(id) {{
            const element = document.getElementById(id);
            element.classList.toggle('show');
        }}
    </script>
</body>
</html>"""

STATUS_PAGE_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>Bluesky Bot Status</title>
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
            margin-bottom: 40px;
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
            font-size: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .status-value {{
            font-size: 2rem;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .status-label {{
            color: #888;
            font-size: 0.9rem;
        }}
        .status-active {{
            color: #00ff88;
        }}
        .status-inactive {{
            color: #ff4444;
        }}
        .uptime {{
            font-size: 1.2rem;
            margin-bottom: 5px;
        }}
        .ai-mode {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 0.9rem;
            background: #00a8ff22;
            color: #00a8ff;
            border: 1px solid #00a8ff44;
        }}
        .ai-mode.placeholder {{
            background: #ff444422;
            color: #ff8888;
            border-color: #ff444444;
        }}
        .footer {{
            margin-top: 40px;
            text-align: center;
            color: #666;
            font-size: 0.9rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 {bot_name} Status</h1>
        
        <div class="status-grid">
            <div class="status-card">
                <h3>Bot Status</h3>
                <div class="status-value {status_class}">{status}</div>
                <div class="uptime">{uptime}</div>
                <div style="margin-top: 10px;">
                    <span class="ai-mode {ai_mode_class}">{ai_mode}</span>
                </div>
            </div>
            
            <div class="status-card">
                <h3>Activity</h3>
                <div class="status-value">{mentions}</div>
                <div class="status-label">Mentions received</div>
                <div style="margin-top: 10px;">
                    <div class="status-value">{responses}</div>
                    <div class="status-label">Responses sent</div>
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
                <div class="status-value">{errors}</div>
                <div class="status-label">Errors encountered</div>
            </div>
        </div>
        
        <div class="footer">
            <p>Auto-refreshes every 10 seconds</p>
        </div>
    </div>
</body>
</html>"""


def build_response_cards_html(responses: list["ResponseContext"]) -> str:
    """Build HTML for response cards"""
    if not responses:
        return '<p style="text-align: center; color: #888;">No recent responses to display.</p>'
    
    return "".join([
        f'''
        <div class="response-card">
            <div class="response-header">
                <div class="response-meta">
                    {resp.timestamp[:19].replace("T", " ")} • @{resp.author_handle}
                    {f" • Thread: {resp.thread_uri.split('/')[-1][:8]}..." if resp.thread_uri else ""}
                </div>
                <div class="mention-text">"{resp.mention_text}"</div>
                <div class="generated-response">→ "{resp.generated_response}"</div>
                <div class="stats">
                    <div class="stat">{len(resp.components)} components</div>
                    <div class="stat">{resp.total_context_chars:,} characters</div>
                </div>
            </div>
            <div class="components">
                {"".join([
                    f'''
                <div class="component">
                    <div class="component-header" onclick="toggleComponent('{resp.response_id}_{i}')">
                        <div>
                            <strong>{comp.name}</strong>
                            <span class="component-type">{comp.type}</span>
                        </div>
                        <div class="component-size">{comp.size_chars:,} chars</div>
                    </div>
                    <div class="component-content" id="{resp.response_id}_{i}">
{comp.content}
                    </div>
                </div>
                '''
                    for i, comp in enumerate(resp.components)
                ])}
            </div>
        </div>
        '''
        for resp in responses
    ])