#!/usr/bin/env python3
"""
Simple Web UI for qBittorrent Downloads
Access: https://qb.nightsub.ir (Basic Auth: Night_Walker / 7798)
"""
import asyncio
import json
from aiohttp import web
import aiohttp
import os
import base64

QB_URL = "http://localhost:8083"
username = None
password = None
AUTH_HEADER = None

async def get_qb_torrents():
    """Get torrents from qBittorrent"""
    global AUTH_HEADER
    try:
        # Get temp password from logs
        import subprocess
        result = subprocess.run(
            ["journalctl", "-u", "qbittorrent", "-n", "50", "--no-pager"],
            capture_output=True, text=True
        )
        for line in result.stdout.split('\n'):
            if 'WebUI' in line and 'Local' in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == 'Username:' and i+1 < len(parts):
                        username = parts[i+1]
                    if p == 'Password:' and i+1 < len(parts):
                        password = parts[i+1]
                        break
        
        if not locals().get("username") or not locals().get("password"):
            username, password = "admin", "adminadmin"
        
        # Authenticate
        async with aiohttp.ClientSession() as session:
            auth_resp = await session.post(
                f"{QB_URL}/api/v2/auth/login",
                data={"username": username, "password": password}
            )
            cookies = auth_resp.cookies
            
            # Get torrents
            torrents_resp = await session.get(
                f"{QB_URL}/api/v2/torrents/info",
                cookies=cookies
            )
            torrents = await torrents_resp.json()
            
            return torrents
    except Exception as e:
        return {"error": str(e)}

def format_size(bytes_val):
    """Format bytes to human readable"""
    try:
        b = int(bytes_val)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} PB"
    except:
        return "?"

def get_status_emoji(state):
    """Get emoji for torrent state"""
    states = {
        'downloading': '⬇️',
        'uploading': '⬆️',
        'paused': '⏸️',
        'checking': '🔍',
        'queued': '⏳',
        'error': '❌',
        'forced': '⚡'
    }
    return states.get(state.lower(), '❓')

async def index(request):
    torrents = await get_qb_torrents()
    
    if isinstance(torrents, dict) and 'error' in torrents:
        return web.Response(text=f"<h1>Error: {torrents['error']}</h1>", content_type='text/html')
    
    html = """<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🦞 Night Leecher - qBittorrent</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: 'Tahoma', 'Segoe UI', sans-serif; 
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 20px;
            margin-bottom: 30px;
        }
        .header h1 { font-size: 2em; margin-bottom: 10px; }
        .header .lobster { font-size: 3em; }
        .stats {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }
        .stat-box {
            background: rgba(255,255,255,0.1);
            padding: 20px 30px;
            border-radius: 15px;
            text-align: center;
        }
        .stat-box .num { font-size: 2em; font-weight: bold; }
        .stat-box .label { opacity: 0.7; margin-top: 5px; }
        .torrents {
            max-width: 1000px;
            margin: 0 auto;
        }
        .torrent {
            background: rgba(255,255,255,0.05);
            margin-bottom: 15px;
            border-radius: 10px;
            padding: 15px 20px;
            display: flex;
            align-items: center;
            gap: 15px;
            flex-wrap: wrap;
        }
        .torrent .status { font-size: 1.5em; }
        .torrent .info { flex: 1; min-width: 200px; }
        .torrent .name { font-weight: bold; margin-bottom: 5px; font-size: 1.1em; }
        .torrent .meta { font-size: 0.85em; opacity: 0.7; }
        .torrent .progress-bar {
            width: 100%;
            height: 8px;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            margin-top: 10px;
            overflow: hidden;
        }
        .torrent .progress {
            height: 100%;
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            border-radius: 4px;
            transition: width 0.3s;
        }
        .torrent .progress.done { background: linear-gradient(90deg, #00ff88, #00d4ff); }
        .seeding { border-right: 4px solid #00ff88; }
        .downloading { border-right: 4px solid #00d4ff; }
        .paused { border-right: 4px solid #ffaa00; }
        .badge {
            padding: 3px 8px;
            border-radius: 5px;
            font-size: 0.75em;
            font-weight: bold;
        }
        .badge-private { background: #9b59b6; }
        .badge-public { background: #3498db; }
        .no-torrents {
            text-align: center;
            padding: 50px;
            opacity: 0.5;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="lobster">🦞</div>
        <h1>🌊 Night Leecher</h1>
        <p>qBittorrent Downloads & Seeding</p>
    </div>
    
    <div class="stats">
        <div class="stat-box">
            <div class="num">""" + str(len(torrents)) + """</div>
            <div class="label">کل دانلودها</div>
        </div>
        <div class="stat-box">
            <div class="num">""" + str(len([t for t in torrents if t.get('state') == 'uploading'])) + """</div>
            <div class="label">سیدینگ</div>
        </div>
        <div class="stat-box">
            <div class="num">""" + str(len([t for t in torrents if t.get('state') == 'downloading'])) + """</div>
            <div class="label">دانلود</div>
        </div>
    </div>
    
    <div class="torrents">
"""
    
    if not torrents:
        html += '<div class="no-torrents">هیچ دانلودی نیست 🦞</div>'
    else:
        for t in torrents:
            state = t.get('state', 'unknown')
            progress = t.get('progress', 0) * 100
            size = format_size(t.get('size', 0))
            downloaded = format_size(t.get('downloaded', 0))
            up_speed = format_size(t.get('upspeed', 0))
            down_speed = format_size(t.get('dlspeed', 0))
            seeds = t.get('num_seeds', 0)
            peers = t.get('num_peers', 0)
            name = t.get('name', 'Unknown')
            category = t.get('category', 'public')
            
            status_class = 'downloading'
            if state == 'uploading':
                status_class = 'seeding'
            elif state == 'paused':
                status_class = 'paused'
            
            badge_class = 'badge-public'
            if category == 'private':
                badge_class = 'badge-private'
            
            status_emoji = get_status_emoji(state)
            
            if state == 'downloading':
                status_text = f"⬇️ دانلود {down_speed}/ثانیه"
                progress_bar = f'<div class="progress-bar"><div class="progress" style="width:{progress:.1f}%"></div></div>'
            elif state == 'uploading':
                status_text = f"⬆️ سید {up_speed}/ثانیه • {seeds} seeds • {peers} peers"
                progress_bar = f'<div class="progress-bar"><div class="progress done" style="width:100%"></div></div>'
            else:
                status_text = state
                progress_bar = f'<div class="progress-bar"><div class="progress" style="width:{progress:.1f}%"></div></div>'
            
            html += f"""
        <div class="torrent {status_class}">
            <div class="status">{status_emoji}</div>
            <div class="info">
                <div class="name">{name[:60]}{'...' if len(name) > 60 else ''}</div>
                <div class="meta">
                    📦 {size} | 📥 {downloaded} | {status_text}
                    <span class="badge {badge_class}">{category}</span>
                </div>
                {progress_bar}
            </div>
        </div>
"""
    
    html += """
    </div>
    
    <script>
        // Auto-refresh every 30 seconds
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>"""
    
    return web.Response(text=html, content_type='text/html')

async def api_torrents(request):
    """API endpoint for torrents JSON"""
    torrents = await get_qb_torrents()
    return web.json_response(torrents)

app = web.Application()
app.router.add_get('/', index)
app.router.add_get('/api/torrents', api_torrents)

if __name__ == '__main__':
    print("Starting Night Leecher UI on port 8085...")
    web.run_app(app, host='0.0.0.0', port=8085)
