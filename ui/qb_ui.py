#!/usr/bin/env python3
"""
Night Leecher qBittorrent Web UI
"""
import asyncio
import os
from pathlib import Path
from aiohttp import web
import aiohttp

QB_URL = os.environ.get('QBITTORRENT_URL', 'http://localhost:8083')

def load_qb_creds():
    config_path = Path(__file__).parent.parent / "config.env"
    user, pwd = "admin", "adminadmin"
    if config_path.exists():
        with open(config_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('QBITTORRENT_USER='):
                    user = line.split('=', 1)[1].strip()
                elif line.startswith('QBITTORRENT_PASS='):
                    pwd = line.split('=', 1)[1].strip()
    return user, pwd

QB_USER, QB_PASS = load_qb_creds()
_qb_cookies: dict = {}

async def qb_login():
    global _qb_cookies
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{QB_URL}/api/v2/auth/login",
                data={"username": QB_USER, "password": QB_PASS},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                text = await r.text()
                if text.strip() == "Ok.":
                    _qb_cookies = {k: v.value for k, v in r.cookies.items()}
                    return True
    except:
        pass
    return False

async def get_qb_torrents():
    global _qb_cookies
    if not _qb_cookies:
        await qb_login()
    try:
        async with aiohttp.ClientSession(cookies=_qb_cookies) as s:
            async with s.get(
                f"{QB_URL}/api/v2/torrents/info",
                timeout=aiohttp.ClientTimeout(total=15)
            ) as r:
                if r.status == 403:
                    await qb_login()
                    async with aiohttp.ClientSession(cookies=_qb_cookies) as s2:
                        async with s2.get(f"{QB_URL}/api/v2/torrents/info") as r2:
                            if r2.status == 200:
                                return await r2.json()
                if r.status == 200:
                    return await r.json()
    except Exception as e:
        return {"error": str(e)}
    return []

def format_size(bytes_val):
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
    return {
        'downloading': '⬇️', 'uploading': '⬆️', 'paused': '⏸️',
        'pausedDL': '⏸️', 'pausedUP': '⏸️', 'checking': '🔍',
        'queued': '⏳', 'error': '❌', 'forced': '⚡',
        'stalledDL': '🔄', 'stalledUP': '🔄',
    }.get(state, '❓')

async def index(request):
    torrents = await get_qb_torrents()
    if isinstance(torrents, dict) and 'error' in torrents:
        return web.Response(text=f"<h1>Error: {torrents['error']}</h1>", content_type='text/html')

    active_dl = sum(1 for t in torrents if t.get('state') in ('downloading','stalledDL'))
    active_ul = sum(1 for t in torrents if t.get('state') == 'uploading')

    html_rows = ""
    for t in torrents:
        state     = t.get('state', 'unknown')
        progress  = t.get('progress', 0) * 100
        size      = format_size(t.get('size', 0))
        downloaded= format_size(t.get('downloaded', 0))
        up_speed  = format_size(t.get('upspeed', 0))
        down_speed= format_size(t.get('dlspeed', 0))
        seeds     = t.get('num_seeds', 0)
        peers     = t.get('num_peers', 0)
        name      = t.get('name', 'Unknown')
        category  = t.get('category', '')

        status_class = 'downloading'
        if state == 'uploading':
            status_class = 'seeding'
        elif state in ('paused', 'pausedDL', 'pausedUP'):
            status_class = 'paused'

        if state == 'downloading':
            status_text = f"⬇️ {down_speed}/s"
        elif state == 'uploading':
            status_text = f"⬆️ {up_speed}/s • {seeds} seeds"
        else:
            status_text = state

        eta = t.get('eta', 0)
        eta_str = ""
        if eta > 0 and eta < 8640000:
            if eta >= 3600:
                eta_str = f" • ETA: {eta//3600}h{(eta%3600)//60}m"
            elif eta >= 60:
                eta_str = f" • ETA: {eta//60}m{eta%60}s"
            else:
                eta_str = f" • ETA: {eta}s"

        badge = f'<span class="badge badge-{"private" if "private" in category.lower() else "public"}">{category or "public"}</span>' if category else ''

        html_rows += f"""
        <div class="torrent {status_class}">
            <div class="status-icon">{get_status_emoji(state)}</div>
            <div class="info">
                <div class="name" title="{name}">{name[:70]}{'...' if len(name)>70 else ''} {badge}</div>
                <div class="meta">📦 {size} | 📥 {downloaded} | {status_text}{eta_str}</div>
                <div class="progress-bar">
                    <div class="progress {'done' if progress >= 100 else ''}" style="width:{min(100,progress):.1f}%"></div>
                </div>
                <div class="meta-small">{progress:.1f}% | 👥 {peers} peers</div>
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="30">
    <title>🦞 Night Leecher</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Tahoma', sans-serif; background: #0f0f1a; color: #e0e0e0; padding: 15px; }}
        .header {{ text-align: center; padding: 20px; margin-bottom: 20px; }}
        .header h1 {{ font-size: 1.8em; color: #00d4ff; }}
        .stats {{ display: flex; justify-content: center; gap: 15px; flex-wrap: wrap; margin-bottom: 20px; }}
        .stat {{ background: rgba(0,212,255,0.1); border: 1px solid rgba(0,212,255,0.3); padding: 12px 20px; border-radius: 10px; text-align: center; }}
        .stat .num {{ font-size: 1.6em; color: #00d4ff; font-weight: bold; }}
        .stat .lbl {{ font-size: 0.8em; opacity: 0.7; margin-top: 3px; }}
        .torrents {{ max-width: 900px; margin: 0 auto; }}
        .torrent {{ background: rgba(255,255,255,0.04); border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; display: flex; gap: 14px; align-items: flex-start; border-right: 4px solid #666; }}
        .torrent.downloading {{ border-right-color: #00d4ff; }}
        .torrent.seeding {{ border-right-color: #00ff88; }}
        .torrent.paused {{ border-right-color: #ffaa00; }}
        .status-icon {{ font-size: 1.4em; min-width: 30px; }}
        .info {{ flex: 1; }}
        .name {{ font-weight: bold; margin-bottom: 6px; word-break: break-all; }}
        .meta {{ font-size: 0.82em; opacity: 0.7; margin-bottom: 6px; }}
        .meta-small {{ font-size: 0.75em; opacity: 0.5; margin-top: 4px; }}
        .progress-bar {{ width: 100%; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden; }}
        .progress {{ height: 100%; background: linear-gradient(90deg, #00d4ff, #00ff88); border-radius: 3px; }}
        .progress.done {{ background: #00ff88; }}
        .badge {{ padding: 2px 7px; border-radius: 4px; font-size: 0.72em; font-weight: bold; margin-right: 5px; }}
        .badge-private {{ background: #9b59b6; color: #fff; }}
        .badge-public {{ background: #2980b9; color: #fff; }}
        .empty {{ text-align: center; padding: 60px; opacity: 0.4; font-size: 1.2em; }}
    </style>
</head>
<body>
    <div class="header"><h1>🦞 Night Leecher</h1><p>qBittorrent Monitor</p></div>
    <div class="stats">
        <div class="stat"><div class="num">{len(torrents)}</div><div class="lbl">📥 کل</div></div>
        <div class="stat"><div class="num">{active_dl}</div><div class="lbl">⬇️ دانلود</div></div>
        <div class="stat"><div class="num">{active_ul}</div><div class="lbl">⬆️ سیدینگ</div></div>
    </div>
    <div class="torrents">
        {"<div class='empty'>هیچ دانلودی وجود ندارد 🦞</div>" if not torrents else html_rows}
    </div>
</body>
</html>"""

    return web.Response(text=html, content_type='text/html')

async def api_torrents(request):
    return web.json_response(await get_qb_torrents())

app = web.Application()
app.router.add_get('/', index)
app.router.add_get('/api/torrents', api_torrents)

if __name__ == '__main__':
    print("Starting Night Leecher qB UI on port 8085...")
    web.run_app(app, host='0.0.0.0', port=8085)
