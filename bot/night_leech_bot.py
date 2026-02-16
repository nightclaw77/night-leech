#!/usr/bin/env python3
"""
Night Leech Bot - Simplified & Reliable
- Shows raw results by default (newest first)
- Groups by quality when clear
- Simple season/episode detection
"""

import os, asyncio, logging, aiohttp, xml.etree.ElementTree as ET, re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters, InlineQueryHandler

BOT_TOKEN = "8237711641:AAFACjgYYAJpV4oWa-aDoRcGwTipcOUFLyY"
JACKETT_URL = "http://localhost:9117"
JACKETT_API_KEY = "3kknp1d7trlr6tp95apmcwndu53d0cm9"
QBITTORRENT_URL = "http://localhost:8083"
FILE_SERVER_URL = "https://files.nightsub.ir"

# Indexers
INDEXERS = [
    ("torrentgalaxyclone", "TorrentGalaxy 🌐"),
    ("subsplease", "SubsPlease 📺"),
    ("eztv", "EZTV 📺"),
    ("iptorrents", "IPTorrents 🔒"),
]

ITEMS_PER_PAGE = 8
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.FileHandler('/root/.openclaw/workspace/Night-Leech/logs/bot.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def fmt_size(s):
    try:
        v = int(s)
        if v >= 1073741824: return f"{v/1073741824:.1f}GB"
        elif v >= 1048576: return f"{v/1048576:.1f}MB"
        else: return f"{v/1024:.1f}KB"
    except: return "?"

def parse_title(title):
    """Simple title parsing"""
    result = {
        'season': None, 'episode': None, 
        'quality': 'Unknown', 'is_tv': False, 
        'title': title
    }
    
    # Quality
    q = re.search(r'(4K|2160p|1080p|720p|480p|540p)', title, re.I)
    if q:
        result['quality'] = q.group(1).upper().replace('2160P', '4K')
    
    # S01E01 or S1E1
    m = re.search(r'[Ss](\d+)[Ee](\d+)', title)
    if m:
        result['season'] = int(m.group(1))
        result['episode'] = int(m.group(2))
        result['is_tv'] = True
    
    # Season X or Season 1
    if not result['is_tv']:
        m = re.search(r'[Ss]eason[\s._-]*(\d+)', title, re.I)
        if m:
            result['season'] = int(m.group(1))
            result['is_tv'] = True
    
    # Standalone S01 (not followed by E)
    if not result['is_tv']:
        m = re.search(r'[Ss](\d+)(?:\s|[^E]|$)', title)
        if m:
            result['season'] = int(m.group(1))
            result['is_tv'] = True
    
    return result

def parse_pubdate(pub):
    try:
        return datetime.strptime(pub[:25], "%a, %d %b %Y %H:%M:%S") if pub else datetime.min
    except: return datetime.min

async def search_jackett(query, indexer_filter=None):
    """Search Jackett - returns all results sorted by date"""
    try:
        import urllib.parse
        results = []
        indexers = [indexer_filter] if indexer_filter else [x[0] for x in INDEXERS]
        
        for idx_id in indexers:
            try:
                params = urllib.parse.urlencode({
                    "apikey": JACKETT_API_KEY, 
                    "t": "search", 
                    "q": query,
                    "sort": "date",
                    "order": "desc"
                })
                url = f"{JACKETT_URL}/api/v2.0/indexers/{idx_id}/results/torznab/api?{params}"
                
                async with aiohttp.ClientSession() as s:
                    async with s.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
                        if r.status == 200:
                            text = await r.text()
                            if '<item>' in text:
                                root = ET.fromstring(text)
                                for item in root.findall('.//item'):
                                    title = item.find('title').text or "?"
                                    comments = item.find('comments').text or ""
                                    magnet = comments if comments.startswith('magnet:') else ""
                                    
                                    parsed = parse_title(title)
                                    
                                    results.append({
                                        "Title": title,
                                        "Magnet": magnet,
                                        "Size": item.find('size').text or "0",
                                        "Seeders": item.find('.//torznab[@name="seeders"]').get('value', '0') if item.find('.//torznab[@name="seeders"]') is not None else '0',
                                        "Indexer": idx_id,
                                        "PubDate": item.find('pubDate').text or "",
                                        "ParsedDate": parse_pubdate(item.find('pubDate').text),
                                        **parsed
                                    })
            except Exception as e:
                logger.error(f"Jackett {idx_id}: {e}")
        
        # Sort by date descending (newest first)
        results.sort(key=lambda x: x.get("ParsedDate") or datetime.min, reverse=True)
        return results
        
    except Exception as e:
        logger.error(f"Jackett error: {e}")
    return []

async def qbit_add_magnet(magnet):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{QBITTORRENT_URL}/api/v2/torrents/add", data={"urls": magnet}) as r:
                return r.status == 200
    except: return False

async def qbit_get_torrents():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{QBITTORRENT_URL}/api/v2/torrents/info") as r:
                if r.status == 200: return await r.json()
    except: pass
    return []

async def qbit_get_files(hash):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{QBITTORRENT_URL}/api/v2/torrents/files?hash={hash}") as r:
                if r.status == 200: return await r.json()
    except: pass
    return []

async def get_imdb_posters(query):
    try:
        import urllib.parse
        q = query.replace(' ', '%20').strip()
        if not q: return None
        url = f"https://v2.sg.media-imdb.com/suggestion/{q[0].lower()}/{q}.json"
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    d = await r.json()
                    return [{"title": x.get("l", "?"), "year": x.get("y", "?"), "poster": x.get("i", {}).get("imageUrl", "")} for x in d.get("d", [])[:10]]
    except: pass
    return None

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Downloads", callback_data="downloads")],
        [InlineKeyboardButton("⚙️ Status", callback_data="status")]
    ])

def indexer_buttons(current):
    kb = []
    for idx_id, display in INDEXERS:
        prefix = "✅" if current == idx_id else "⬜"
        kb.append([InlineKeyboardButton(f"{prefix} {display}", callback_data=f"filter_{idx_id}")])
    if current:
        kb.append([InlineKeyboardButton("🔄 All", callback_data="filter_all")])
    return kb

def paginate(page, total):
    kb, nav = [], []
    if page > 0: nav.append(InlineKeyboardButton("◀️", callback_data=f"p_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total}", callback_data="noop"))
    if page < total-1: nav.append(InlineKeyboardButton("▶️", callback_data=f"p_{page+1}"))
    kb.append(nav)
    return kb

async def show_results(update, ctx, msg):
    """Show all results in a simple list"""
    items = ctx.user_data.get("results", [])
    title = ctx.user_data.get("search_title", "")
    page = ctx.user_data.get("page", 0)
    filter_idx = ctx.user_data.get("filter_indexer")
    
    if not items:
        await msg.edit_text("❌ No results.")
        return
    
    total = (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    start = page * ITEMS_PER_PAGE
    
    kb = []
    text = f"🔍 *{title}*\n\nFound *{len(items)}* results | 🆕 Newest\n\n"
    
    for i, t in enumerate(items[start:start + ITEMS_PER_PAGE]):
        idx_emoji = "🔒" if t.get('Indexer') == 'iptorrents' else "🌐"
        quality = t.get('quality', '?')
        size = fmt_size(t.get('Size', '0'))
        seeders = t.get('Seeders', '0')
        name = t.get('Title', '?')[:45]
        
        # Add S/E info if TV
        se_info = ""
        if t.get('is_tv'):
            s = t.get('season', '')
            e = t.get('episode', '')
            if s and e:
                se_info = f" S{s}E{e}"
            elif s:
                se_info = f" S{s}"
        
        text += f"*{start+i+1}.* {idx_emoji} {quality}{se_info}\n"
        text += f"   {name}\n"
        text += f"   📦 {size} | 👤 {seeders}\n\n"
        
        kb.append([InlineKeyboardButton(f"{idx_emoji} {quality}{se_info} {size}", callback_data=f"t_{start+i}")])
    
    # Navigation and filters
    kb.extend(paginate(page, total))
    kb.extend(indexer_buttons(filter_idx))
    kb.append([InlineKeyboardButton("◀️ Back", callback_data="back")])
    
    try:
        await msg.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    except:
        await msg.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

async def callback_handler(update, ctx):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "back":
        ctx.user_data.clear()
        await query.edit_message_text(
            "🌙 *Night Leech Bot* 🦞\n\n🔍 Type `@NightLeechBot name` to search!",
            parse_mode='Markdown', reply_markup=main_menu()
        )
    
    elif data == "downloads":
        torrents = await qbit_get_torrents()
        if torrents:
            kb = []
            for t in torrents[:10]:
                name = t.get('name', '?')[:35]
                progress = t.get('progress', 0) * 100
                bar = "█" * int(progress/10) + "░" * (10 - int(progress/10))
                emoji = "⬇️" if t.get('state') in ['downloading', 'stalledDL'] else "✅"
                kb.append([InlineKeyboardButton(f"{emoji} {name[:25]}\n{bar} {progress:.0f}%", callback_data=f"dl_{t.get('hash', '')}")])
            kb.extend([[InlineKeyboardButton("🔄 Refresh", callback_data="downloads")], [InlineKeyboardButton("◀️ Back", callback_data="back")]])
            await query.edit_message_text(f"📥 Downloads ({len(torrents)}):", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await query.edit_message_text("📥 No downloads.", reply_markup=main_menu())
    
    elif data.startswith("dl_"):
        h = data.split("_")[1]
        torrents = await qbit_get_torrents()
        t = next((x for x in torrents if x.get('hash') == h), None)
        if t:
            progress = t.get('progress', 0) * 100
            bar = "█" * int(progress/10) + "░" * (10 - int(progress/10))
            info = f"🎬 {t.get('name', '?')[:50]}\n\n📊 {bar} {progress:.1f}%\n📦 {fmt_size(t.get('downloaded', 0))} / {fmt_size(t.get('size', 0))}\n🔰 {t.get('state', '?')}"
            if progress >= 1.0:
                files = await qbit_get_files(h)
                if files:
                    fn = files[0].get('name', t.get('name', ''))
                    info += f"\n\n🔗 {FILE_SERVER_URL}/download/{fn}"
            kb = [[InlineKeyboardButton("🗑️ Delete", callback_data=f"del_{h}")], [InlineKeyboardButton("◀️ Back", callback_data="downloads")]]
            await query.edit_message_text(info, reply_markup=InlineKeyboardMarkup(kb))
    
    elif data.startswith("del_"):
        h = data.split("_")[1]
        try:
            async with aiohttp.ClientSession() as s:
                await s.post(f"{QBITTORRENT_URL}/api/v2/torrents/delete", data={"hashes": h, "deleteFiles": True})
        except: pass
        await query.edit_message_text("✅ Deleted!", reply_markup=main_menu())
    
    elif data.startswith("filter_"):
        idx = None if data == "filter_all" else data.replace("filter_", "")
        ctx.user_data["filter_indexer"] = idx
        ctx.user_data["page"] = 0
        
        title = ctx.user_data.get("search_title", "")
        results = await search_jackett(title, idx)
        ctx.user_data["results"] = results
        
        await show_results(update, ctx, query)
    
    elif data.startswith("p_"):
        ctx.user_data["page"] = int(data.split("_")[1])
        await show_results(update, ctx, query)
    
    elif data.startswith("t_"):
        idx = int(data.split("_")[1])
        items = ctx.user_data.get("results", [])
        if idx < len(items):
            t = items[idx]
            magnet = t.get("Magnet", "")
            if magnet and await qbit_add_magnet(magnet):
                await query.edit_message_text(
                    f"✅ Added!\n\n🎬 {t['Title'][:50]}\n📦 {fmt_size(t.get('Size', '0'))}\n👤 {t.get('Seeders', '0')} seeders",
                    reply_markup=main_menu()
                )
            else:
                await query.edit_message_text("❌ Failed to add.", reply_markup=main_menu())
    
    elif data == "status":
        torrents = await qbit_get_torrents()
        active = len([t for t in torrents if t.get('state') in ['downloading', 'stalledDL']])
        seeding = len([t for t in torrents if t.get('state') == 'uploading'])
        total = sum([t.get('size', 0) for t in torrents])
        await query.edit_message_text(
            f"⚙️ Status\n\n✅ Bot: Online\n📥 Torrents: {len(torrents)}\n⬇️ Downloading: {active}\n⬆️ Seeding: {seeding}\n💾 Total: {fmt_size(total)}",
            reply_markup=main_menu()
        )

async def imdb_command(update, ctx):
    if not update.message or not update.message.text:
        return
    
    search_q = update.message.text[6:].strip()
    if not search_q:
        return
    
    msg = await update.message.reply_text(f"🔍 Searching: {search_q}")
    
    results = await search_jackett(search_q)
    
    if results:
        ctx.user_data["results"] = results
        ctx.user_data["search_title"] = search_q
        ctx.user_data["page"] = 0
        ctx.user_data["filter_indexer"] = None
        await show_results(update, ctx, msg)
    else:
        await msg.edit_text("❌ No results found.", reply_markup=main_menu())

async def inline_query(update, ctx):
    query = update.inline_query.query
    if not query or len(query) < 2:
        return
    
    results = await get_imdb_posters(query)
    if not results:
        return
    
    articles = []
    for i, item in enumerate(results):
        articles.append(InlineQueryResultArticle(
            id=str(i),
            title=f"{item['title']} ({item['year']})",
            description="🎬 Tap to search",
            thumbnail_url=item.get('poster', ''),
            input_message_content=InputTextMessageContent(message_text=f"/imdb {item['title']} {item['year']}")
        ))
    
    await update.inline_query.answer(articles, cache_time=300, is_personal=True)

async def message_handler(update, ctx):
    await update.message.reply_text(
        "🌙 *Night Leech Bot* 🦞\n\n🔍 Type `@NightLeechBot name` to search!",
        parse_mode='Markdown', reply_markup=main_menu()
    )

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("🌙 Night Leech Bot 🦞\n\n🔍 Type `@NightLeechBot name`!", reply_markup=main_menu())))
    app.add_handler(CommandHandler("imdb", imdb_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(InlineQueryHandler(inline_query))
    logger.info("Night Leech Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()
