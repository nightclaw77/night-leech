#!/usr/bin/env python3
"""
Night Leecher File Server UI - Fixed Version
"""
import asyncio
import aiohttp
import subprocess
import os
from aiohttp import web
import urllib.parse

PORT = 8086
BASE_DIR = "/root/.openclaw/workspace/Night-Leech/downloads/qbittorrent/Downloads"

def format_size(size):
    try:
        size = int(size)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
    except:
        return "?"

def get_icon(filename):
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    icons = {
        'mkv': '🎬', 'mp4': '🎬', 'avi': '🎬', 'mov': '🎬',
        'mp3': '🎵', 'flac': '🎵', 'wav': '🎵',
        'jpg': '🖼️', 'png': '🖼️', 'gif': '🖼️',
        'zip': '📦', 'rar': '📦', '7z': '📦',
        'txt': '📄', 'pdf': '📄', 'nfo': '📄',
        'srt': '📝'
    }
    return icons.get(ext, '📁')

async def get_torrents():
    try:
        username, password = "admin", "adminadmin"
        async with aiohttp.ClientSession() as session:
            async with session.post("http://localhost:8083/api/v2/auth/login",
                data={"username": username, "password": password}) as resp:
                cookies = resp.cookies
            async with session.get("http://localhost:8083/api/v2/torrents/info",
                cookies=cookies) as resp:
                return await resp.json()
    except:
        return []

def list_dir(path):
    items = []
    try:
        for item in os.listdir(path):
            full = os.path.join(path, item)
            is_dir = os.path.isdir(full)
            stat = os.stat(full)
            size = stat.st_size if not is_dir else 0
            items.append({
                'name': item,
                'path': os.path.relpath(full, BASE_DIR),
                'size': format_size(size),
                'is_dir': is_dir,
                'icon': '📁' if is_dir else get_icon(item)
            })
        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    except Exception as e:
        print(f"Error listing {path}: {e}")
    return items

def get_breadcrumbs(path):
    parts = path.split('/')
    crumbs = []
    current = ""
    for part in parts:
        current = os.path.join(current, part)
        if part:
            crumbs.append({'name': part, 'path': current if current != '.' else ''})
    return crumbs

async def index(request):
    path = request.query.get('path', '')
    if path == '.' or path == '..':
        path = ''
    
    full_path = os.path.join(BASE_DIR, path) if path else BASE_DIR
    
    # Security: prevent directory traversal
    real_base = os.path.realpath(BASE_DIR)
    try:
        if not os.path.realpath(full_path).startswith(real_base):
            return web.Response(text="Invalid path", status=403)
    except:
        return web.Response(text="Invalid path", status=403)
    
    items = list_dir(full_path)
    torrents = await get_torrents()
    breadcrumbs = get_breadcrumbs(path)
    
    # Build HTML
    torrents_count = len(torrents)
    seeding_count = len([t for t in torrents if t.get('state') == 'uploading'])
    downloading_count = len([t for t in torrents if t.get('state') == 'downloading'])
    
    html_parts = ["""<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🦞 Night Leecher - Files</title>
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap" rel="stylesheet">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Vazirmatn', sans-serif; background: #0f0f23; color: #fff; min-height: 100vh; }
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }
.header { text-align: center; padding: 20px; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 15px; margin-bottom: 20px; }
.header h1 { font-size: 2em; }
.stats { display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; margin-bottom: 20px; }
.stat { background: rgba(255,255,255,0.05); padding: 15px 25px; border-radius: 10px; text-align: center; }
.stat .num { font-size: 1.5em; color: #00d4ff; font-weight: bold; }
.section { background: rgba(255,255,255,0.03); border-radius: 15px; padding: 20px; margin-bottom: 20px; }
.section h2 { margin-bottom: 15px; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px; text-align: right; border-bottom: 1px solid rgba(255,255,255,0.05); }
th { opacity: 0.5; }
tr:hover { background: rgba(255,255,255,0.03); }
a { color: #00d4ff; text-decoration: none; }
a:hover { text-decoration: underline; }
.icon { font-size: 1.3em; margin-left: 8px; }
.btn { display: inline-block; padding: 8px 15px; background: linear-gradient(135deg, #00d4ff, #00ff88); color: #000; border-radius: 8px; text-decoration: none; font-weight: bold; }
.btn:hover { transform: scale(1.05); }
.breadcrumb { margin-bottom: 15px; opacity: 0.7; }
.breadcrumb a { margin: 0 5px; }
.breadcrumb span { margin: 0 5px; }
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>🌊 Night Leecher</h1>
<p>File Server & Downloads</p>
</div>
<div class="stats">
<div class="stat"><div class="num">""", str(torrents_count), """</div><div>📥 Torrents</div></div>
<div class="stat"><div class="num">""", str(seeding_count), """</div><div>⬆️ Seeding</div></div>
<div class="stat"><div class="num">""", str(downloading_count), """</div><div>⬇️ Downloading</div></div>
<div class="stat"><div class="num">""", str(len(items)), """</div><div>📁 Files</div></div>
</div>
<div class="section">
<h2>📁 Files</h2>
<div class="breadcrumb">"""]
    
    # Breadcrumb
    if breadcrumbs:
        html_parts.append('<a href="/">🏠 Home</a>')
        for i, crumb in enumerate(breadcrumbs):
            if i == len(breadcrumbs) - 1:
                html_parts.append(f'<span>👉 {crumb["name"]}</span>')
            else:
                html_parts.append(f'<span>›</span><a href="/?path={urllib.parse.quote(crumb["path"])}">{crumb["name"]}</a>')
    
    html_parts.append('</div><table><tr><th></th><th>نام</th><th>اندازه</th><th>عملیات</th></tr>')
    
    if not items:
        html_parts.append('<tr><td colspan="4" style="text-align:center;opacity:0.5">📂 پوشه خالی است</td></tr>')
    else:
        for item in items:
            name = item['name']
            icon = item['icon']
            size = item['size']
            item_path = item['path']
            
            if item['is_dir']:
                html_parts.append(f'''<tr>
<td class="icon">{icon}</td>
<td><a href="/?path={urllib.parse.quote(item_path)}">{name}</a></td>
<td>📁</td>
<td><a href="/?path={urllib.parse.quote(item_path)}" class="btn">📂 باز کردن</a></td>
</tr>''')
            else:
                dl_url = f"/download/{urllib.parse.quote(item_path)}"
                html_parts.append(f'''<tr>
<td class="icon">{icon}</td>
<td>{name}</td>
<td>{size}</td>
<td><a href="{dl_url}" class="btn" target="_blank">⬇️ دانلود</a></td>
</tr>''')
    
    html_parts.append('</table></div></div></body></html>')
    
    return web.Response(text=''.join(html_parts), content_type='text/html')

async def download(request):
    path = request.match_info.get('path', '')
    if not path or path == '.':
        return web.Response(text="Invalid file", status=400)
    
    full_path = os.path.join(BASE_DIR, path)
    
    # Security check
    real_base = os.path.realpath(BASE_DIR)
    try:
        if not os.path.realpath(full_path).startswith(real_base):
            return web.Response(text="Invalid path", status=403)
    except:
        return web.Response(text="Invalid path", status=403)
    
    if not os.path.exists(full_path) or os.path.isdir(full_path):
        return web.Response(text="File not found", status=404)
    
    filename = os.path.basename(full_path)
    file_size = os.path.getsize(full_path)
    
    return web.Response(
        body=open(full_path, 'rb'),
        status=200,
        headers={
            'Content-Type': 'application/octet-stream',
            'Content-Length': str(file_size),
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )

app = web.Application()
app.router.add_get('/', index)
app.router.add_get('/download/{path:.*}', download)

if __name__ == '__main__':
    print(f"🌊 Night Leecher UI starting on port {PORT}...")
    web.run_app(app, host='0.0.0.0', port=PORT)
