"""HTML templates for the bot"""

STATUS_PAGE_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>{bot_name} Status</title>
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
        <h1>🤖 {bot_name} Status</h1>
        
        <div class="status-grid">
            <div class="status-card">
                <h3>Bot Status</h3>
                <div class="status-value">
                    <span class="status-indicator {status_class}"></span>
                    {status_text}
                </div>
                <div class="status-label">@{handle}</div>
            </div>
            
            <div class="status-card">
                <h3>Uptime</h3>
                <div class="status-value">{uptime}</div>
                <div class="status-label">Since startup</div>
            </div>
            
            <div class="status-card">
                <h3>Activity</h3>
                <div class="status-value">{mentions_received}</div>
                <div class="status-label">Mentions received</div>
                <div style="margin-top: 10px;">
                    <div class="status-value">{responses_sent}</div>
                    <div class="status-label">Responses sent</div>
                </div>
            </div>
            
            <div class="status-card">
                <h3>Response Mode</h3>
                <div class="status-value">
                    {ai_mode}
                </div>
                <div class="status-label">
                    {ai_description}
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
