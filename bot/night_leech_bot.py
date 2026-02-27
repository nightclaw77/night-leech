#!/usr/bin/env python3
"""
Night Leech Bot - Ultimate Edition v3
Complete rewrite with all bugs fixed and features added.
"""

import asyncio
import logging
import aiohttp
import re
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from collections import defaultdict
from pathlib import Path

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQueryResultArticle, InputTextMessageContent
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters, InlineQueryHandler
)

# ─── Config Loading ───────────────────────────────────────────────────────────

def load_config():
    """Load config from config.env file or environment variables"""
    config = {}
    config_path = Path(__file__).parent.parent / "config.env"
    if config_path.exists():
        with open(config_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, val = line.partition('=')
                    config[key.strip()] = val.strip()
    # Environment variables override file
    for key in ['BOT_TOKEN', 'JACKETT_URL', 'JACKETT_API_KEY', 'QBITTORRENT_URL',
                'QBITTORRENT_USER', 'QBITTORRENT_PASS', 'FILE_SERVER_URL', 'ALLOWED_USERS']:
        if key in os.environ:
            config[key] = os.environ[key]
    return config

cfg = load_config()

BOT_TOKEN         = cfg.get('BOT_TOKEN', '')
JACKETT_URL       = cfg.get('JACKETT_URL', 'http://localhost:9117')
JACKETT_API_KEY   = cfg.get('JACKETT_API_KEY', '')
QBITTORRENT_URL   = cfg.get('QBITTORRENT_URL', 'http://localhost:8083')
QB_USER           = cfg.get('QBITTORRENT_USER', 'admin')
QB_PASS           = cfg.get('QBITTORRENT_PASS', 'adminadmin')
FILE_SERVER_URL   = cfg.get('FILE_SERVER_URL', 'https://files.nightsub.ir')
_allowed_raw      = cfg.get('ALLOWED_USERS', '').strip()
ALLOWED_USERS     = set(int(x) for x in _allowed_raw.split(',') if x.strip().isdigit()) if _allowed_raw else set()

# Indexers will be read from Jackett config files
_cached_indexers: list = []
_cached_indexers_time: float = 0

import json as json_module

def get_indexers_sync() -> list:
    """Read configured indexers from Jackett config files"""
    global _cached_indexers, _cached_indexers_time
    
    # Cache for 60 seconds
    if _cached_indexers and (time.time() - _cached_indexers_time) < 60:
        return _cached_indexers
    
    indexers = []
    jackett_indexers_path = Path.home() / ".config/Jackett/Indexers"
    
    try:
        if jackett_indexers_path.exists():
            for json_file in sorted(jackett_indexers_path.glob("*.json")):
                # Skip backup files
                if json_file.name.endswith('.bak'):
                    continue
                idx_id = json_file.stem
                
                # Read the config file to get extra info
                try:
                    with open(json_file, 'r') as f:
                        config = json_module.load(f)
                    # Check if it's configured (has a sitelink value)
                    is_configured = False
                    is_private = False
                    for item in config:
                        if item.get('id') == 'sitelink' and item.get('value'):
                            is_configured = True
                        if item.get('id') == 'cookieheader' and item.get('value'):
                            is_private = True
                    if is_configured:
                        emoji = "🔒" if is_private else "🌐"
                        # Capitalize and format the name
                        name = idx_id.replace('_', ' ').title()
                        indexers.append((idx_id, f"{emoji} {name}"))
                except:
                    # If can't read config, just add with default emoji
                    indexers.append((idx_id, f"🌐 {idx_id}"))
        
        _cached_indexers = indexers
        _cached_indexers_time = time.time()
        logger.info(f"Read {len(indexers)} indexers from Jackett config files")
    except Exception as e:
        logger.error(f"Failed to read indexers from Jackett: {e}")
    
    return _cached_indexers if _cached_indexers else []

async def get_indexers() -> list:
    """Async wrapper for get_indexers_sync"""
    return get_indexers_sync()

def get_indexer_display_name(idx_id: str, indexers: list) -> str:
    """Get display name for indexer"""
    for iid, display in indexers:
        if iid == idx_id:
            return display
    return f"🌐 {idx_id}"

def get_indexer_emoji(idx_id: str, indexers: list) -> str:
    """Get emoji for indexer"""
    display = get_indexer_display_name(idx_id, indexers)
    if "🔒" in display:
        return "🔒"
    elif "📺" in display:
        return "📺"
    return "🌐"

ITEMS_PER_PAGE = 5

# ─── Logging ─────────────────────────────────────────────────────────────────

logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(logs_dir / 'bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── qBittorrent Session ─────────────────────────────────────────────────────

_qb_cookies: dict = {}

async def qb_login() -> dict:
    """Login to qBittorrent and return cookies"""
    global _qb_cookies
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{QBITTORRENT_URL}/api/v2/auth/login",
                data={"username": QB_USER, "password": QB_PASS},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                text = await r.text()
                if text.strip() == "Ok.":
                    _qb_cookies = {k: v.value for k, v in r.cookies.items()}
                    logger.info("qBittorrent login successful")
                    return _qb_cookies
                else:
                    logger.error(f"qBittorrent login failed: {text}")
    except Exception as e:
        logger.error(f"qBittorrent login error: {e}")
    return {}

async def qb_request(method: str, path: str, **kwargs):
    """Make authenticated request to qBittorrent, re-login on 403"""
    global _qb_cookies
    if not _qb_cookies:
        await qb_login()
    try:
        async with aiohttp.ClientSession(cookies=_qb_cookies) as s:
            func = s.post if method == 'POST' else s.get
            async with func(
                f"{QBITTORRENT_URL}{path}",
                timeout=aiohttp.ClientTimeout(total=15),
                **kwargs
            ) as r:
                if r.status == 403:
                    # Re-login and retry
                    await qb_login()
                    async with aiohttp.ClientSession(cookies=_qb_cookies) as s2:
                        func2 = s2.post if method == 'POST' else s2.get
                        async with func2(
                            f"{QBITTORRENT_URL}{path}",
                            timeout=aiohttp.ClientTimeout(total=15),
                            **kwargs
                        ) as r2:
                            return r2.status, await r2.text() if 'json' not in kwargs.get('headers', {}).get('Accept', '') else await r2.json()
                if r.status == 200:
                    ct = r.headers.get('Content-Type', '')
                    if 'json' in ct:
                        return r.status, await r.json()
                    return r.status, await r.text()
                return r.status, None
    except Exception as e:
        logger.error(f"qBit request error {path}: {e}")
        return 0, None

async def qbit_add_magnet(magnet: str) -> bool:
    status, _ = await qb_request('POST', '/api/v2/torrents/add', data={"urls": magnet})
    return status == 200

async def qbit_get_torrents() -> list:
    status, data = await qb_request('GET', '/api/v2/torrents/info')
    return data if isinstance(data, list) else []

async def qbit_get_files(hash_: str) -> list:
    status, data = await qb_request('GET', f'/api/v2/torrents/files?hash={hash_}')
    return data if isinstance(data, list) else []

async def qbit_delete(hash_: str) -> bool:
    status, _ = await qb_request('POST', '/api/v2/torrents/delete', data={"hashes": hash_, "deleteFiles": "true"})
    return status == 200

# ─── Utilities ───────────────────────────────────────────────────────────────

def fmt_size(s) -> str:
    try:
        v = int(s)
        if v >= 1_073_741_824: return f"{v/1_073_741_824:.1f}GB"
        if v >= 1_048_576:     return f"{v/1_048_576:.1f}MB"
        return f"{v/1024:.0f}KB"
    except:
        return "?"

def parse_torrent_title(title: str) -> dict:
    """
    Robust torrent title parser for TV shows and movies.
    Handles: S01E01, S1E1, S01 E01, anime - 54 style, Season X, full packs.
    """
    result = {
        'season': None, 'episode': None, 'episodes': [],
        'quality': 'Unknown', 'is_tv': False,
        'is_pack': False, 'clean_title': title
    }

    # Quality detection
    q_match = re.search(r'(4K|2160p|1080p|720p|480p|540p)', title, re.IGNORECASE)
    if q_match:
        q = q_match.group(1).upper()
        result['quality'] = '4K' if q in ('2160P', '4K') else q

    found_se = False

    # Pattern 1: S01E01 or S1E1 (standard)
    m = re.search(r'[Ss](\d+)[Ee](\d+)', title)
    if m:
        result['season']   = int(m.group(1))
        result['episode']  = int(m.group(2))
        result['episodes'] = [int(m.group(2))]
        result['is_tv']    = True
        found_se = True

    # Pattern 2: S01 E01 or S01-E01
    if not found_se:
        m = re.search(r'[Ss](\d+)[ ._-]+[Ee](\d+)', title)
        if m:
            result['season']   = int(m.group(1))
            result['episode']  = int(m.group(2))
            result['episodes'] = [int(m.group(2))]
            result['is_tv']    = True
            found_se = True

    # Pattern 3: Anime style "Title - 54 [quality]"
    if not found_se:
        m = re.search(r'-\s+(\d{2,4})\s', title)
        if m:
            result['episode']  = int(m.group(1))
            result['episodes'] = [int(m.group(1))]
            result['is_tv']    = True

    # Pattern 4: "Season X" full season
    if not found_se:
        m = re.search(r'[Ss]eason\s+(\d+)', title, re.IGNORECASE)
        if m:
            result['season']  = int(m.group(1))
            result['is_tv']   = True
            result['is_pack'] = True
            result['episodes'] = ['pack']
            found_se = True

    # Pattern 5: S01 standalone (season pack)
    if not found_se:
        m = re.search(r'\b[Ss](\d{1,2})\b(?!\s*[Ee]\d)', title)
        if m:
            result['season']  = int(m.group(1))
            result['is_tv']   = True
            result['is_pack'] = True
            result['episodes'] = ['pack']
            found_se = True

    # Infer season from anime episode number (13 eps/season estimate)
    if result['is_tv'] and result['season'] is None and result['episode'] is not None:
        result['season'] = max(1, (result['episode'] - 1) // 13 + 1)

    return result

def parse_pubdate(pub: str) -> datetime:
    try:
        return datetime.strptime(pub[:25], "%a, %d %b %Y %H:%M:%S")
    except:
        return datetime.min

# ─── Jackett Search ───────────────────────────────────────────────────────────

async def search_jackett(query: str, filter_idx: str = None, sort_by: str = "newest") -> list:
    """
    Search Jackett via torznab XML API.
    Falls back to JSON API if XML returns no results.
    Returns list of result dicts.
    """
    import urllib.parse

    results = []
    all_indexers = await get_indexers()
    indexers = [filter_idx] if filter_idx else [x[0] for x in all_indexers]

    async with aiohttp.ClientSession() as session:
        for idx_id in indexers:
            # Try torznab XML first (more reliable for magnet links)
            try:
                params = urllib.parse.urlencode({
                    "apikey": JACKETT_API_KEY,
                    "t": "search",
                    "q": query,
                    "sort": "date",
                    "order": "desc"
                })
                url = f"{JACKETT_URL}/api/v2.0/indexers/{idx_id}/results/torznab/api?{params}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
                    if r.status == 200:
                        text = await r.text()
                        if '<item>' in text:
                            root = ET.fromstring(text)
                            ns = {'torznab': 'http://torznab.com/schemas/2015/feed'}
                            for item in root.findall('.//item'):
                                title_el = item.find('title')
                                title = title_el.text if title_el is not None else '?'

                                # Magnet: check comments first, then enclosure, then link
                                magnet = ''
                                comments_el = item.find('comments')
                                if comments_el is not None and comments_el.text and comments_el.text.startswith('magnet:'):
                                    magnet = comments_el.text
                                else:
                                    # Try torznab magneturl attribute
                                    for attr in item.findall('torznab:attr', ns):
                                        if attr.get('name') == 'magneturl':
                                            magnet = attr.get('value', '')
                                            break
                                    if not magnet:
                                        # Try enclosure url
                                        enc = item.find('enclosure')
                                        if enc is not None:
                                            url_enc = enc.get('url', '')
                                            if url_enc.startswith('magnet:'):
                                                magnet = url_enc
                                            else:
                                                # Use jackett download link as fallback (qBittorrent can handle .torrent URLs)
                                                magnet = url_enc
                                    if not magnet:
                                        # Try link element
                                        link_el = item.find('link')
                                        if link_el is not None and link_el.text:
                                            magnet = link_el.text

                                pub_el = item.find('pubDate')
                                pub = pub_el.text if pub_el is not None else ''
                                size_el = item.find('size')
                                size = size_el.text if size_el is not None else '0'

                                # Seeders from torznab attrs
                                seeders = '0'
                                for attr in item.findall('torznab:attr', ns):
                                    if attr.get('name') == 'seeders':
                                        seeders = attr.get('value', '0')
                                        break

                                parsed = parse_torrent_title(title)
                                results.append({
                                    'Title':      title,
                                    'Magnet':     magnet,
                                    'Size':       size,
                                    'Seeders':    seeders,
                                    'Indexer':    idx_id,
                                    'PubDate':    pub,
                                    'ParsedDate': parse_pubdate(pub),
                                    **parsed
                                })
                            logger.info(f"Jackett XML {idx_id}: {len([x for x in results if x['Indexer']==idx_id])} results")
                            continue
            except Exception as e:
                logger.warning(f"Jackett XML {idx_id} failed: {e}, trying JSON...")

            # Fallback: JSON API
            try:
                params = urllib.parse.urlencode({
                    "apikey": JACKETT_API_KEY,
                    "q": query,
                    "limit": 50,
                })
                url = f"{JACKETT_URL}/api/v2.0/indexers/{idx_id}/results?{params}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
                    if r.status == 200:
                        data = await r.json()
                        for item in data.get('Results', []):
                            title = item.get('Title', '?')
                            # FIX: correct key is MagnetUri, not Magnet
                            magnet = item.get('MagnetUri', '') or item.get('Magnet', '')
                            if not magnet or not magnet.startswith('magnet:'):
                                # Last resort: check if Guid is a magnet
                                guid = item.get('Guid', '')
                                if str(guid).startswith('magnet:'):
                                    magnet = guid
                                else:
                                    # Try Link as fallback
                                    link = item.get('Link', '')
                                    if link and link.startswith('http'):
                                        magnet = link
                            pub = item.get('PublishDate', item.get('FirstSeen', ''))
                            parsed = parse_torrent_title(title)
                            results.append({
                                'Title':      title,
                                'Magnet':     magnet,
                                'Size':       str(item.get('Size', 0)),
                                'Seeders':    str(item.get('Seeders', 0)),
                                'Indexer':    idx_id,
                                'PubDate':    pub,
                                'ParsedDate': parse_pubdate(pub) if pub else datetime.min,
                                **parsed
                            })
                        logger.info(f"Jackett JSON {idx_id}: {len(data.get('Results', []))} results")
            except Exception as e:
                logger.error(f"Jackett JSON {idx_id}: {e}")

    # Sort results
    if sort_by == "seeders":
        results.sort(key=lambda x: int(x.get('Seeders', 0)), reverse=True)
    else:  # newest
        results.sort(key=lambda x: x.get('ParsedDate', datetime.min), reverse=True)

    # Remove duplicates by title (keep highest seeders)
    seen_titles = {}
    deduped = []
    for r in results:
        t = r['Title'].lower().strip()
        if t not in seen_titles:
            seen_titles[t] = True
            deduped.append(r)
    
    logger.info(f"Total results for '{query}': {len(deduped)} (after dedup from {len(results)})")
    return deduped

# ─── IMDB Suggestion ─────────────────────────────────────────────────────────

async def get_imdb_suggestions(query: str) -> list:
    try:
        q = query.strip()
        if not q:
            return []
        safe_q = re.sub(r'[^a-zA-Z0-9 ]', '', q).strip()
        if not safe_q:
            safe_q = q
        url = f"https://v2.sg.media-imdb.com/suggestion/{safe_q[0].lower()}/{safe_q.replace(' ', '%20')}.json"
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    d = await r.json(content_type=None)
                    return [
                        {
                            "title": x.get("l", "?"),
                            "year":  x.get("y", ""),
                            "type":  x.get("q", ""),
                            "poster": x.get("i", {}).get("imageUrl", "") if isinstance(x.get("i"), dict) else ""
                        }
                        for x in d.get("d", [])[:10]
                    ]
    except Exception as e:
        logger.error(f"IMDB suggestion error: {e}")
    return []

# ─── UI Helpers ──────────────────────────────────────────────────────────────

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Downloads", callback_data="downloads")],
        [InlineKeyboardButton("⚙️ Status",    callback_data="status")],
    ])

def sort_buttons(current: str) -> list:
    """Sort buttons with active indicator"""
    top_label = "✅ 👤 Top Seeders" if current == "seeders" else "👤 Top Seeders"
    new_label = "✅ 🆕 Newest"       if current == "newest"  else "🆕 Newest"
    return [[
        InlineKeyboardButton(top_label, callback_data="sort_seeders"),
        InlineKeyboardButton(new_label, callback_data="sort_newest"),
    ]]

async def indexer_buttons(current: str) -> list:
    """Indexer filter buttons"""
    kb = []
    row = []
    indexers = await get_indexers()
    for idx_id, display in indexers:
        prefix = "✅ " if current == idx_id else ""
        row.append(InlineKeyboardButton(f"{prefix}{display}", callback_data=f"idx_{idx_id}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    if current:
        kb.append([InlineKeyboardButton("🔄 All Indexers", callback_data="idx_all")])
    return kb

def paginate_buttons(page: int, total: int, prefix: str = "p") -> list:
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"{prefix}_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total}", callback_data="noop"))
    if page < total - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"{prefix}_{page+1}"))
    return [nav] if nav else []

# ─── Authorization ────────────────────────────────────────────────────────────

def is_authorized(update: Update) -> bool:
    if not ALLOWED_USERS:
        return True
    user = update.effective_user
    return user is not None and user.id in ALLOWED_USERS

async def unauthorized_reply(update: Update):
    await update.effective_message.reply_text("⛔ شما دسترسی به این ربات ندارید.")

# ─── Results Display ──────────────────────────────────────────────────────────

async def show_results(update: Update, ctx: ContextTypes.DEFAULT_TYPE, msg):
    """
    Main result display function.
    - TV shows: Season → Quality → Episode navigation
    - Movies: flat paginated list with sort/filter
    """
    items    = ctx.user_data.get("results", [])
    title    = ctx.user_data.get("search_title", "")
    sort     = ctx.user_data.get("sort", "newest")
    filter_  = ctx.user_data.get("filter_indexer")
    nav_mode = ctx.user_data.get("nav_mode", "auto")  # auto/tv/movie/season/quality
    page     = ctx.user_data.get("page", 0)

    if not items:
        try:
            await msg.edit_text("❌ هیچ نتیجه‌ای پیدا نشد.", reply_markup=main_menu())
        except:
            await msg.reply_text("❌ هیچ نتیجه‌ای پیدا نشد.", reply_markup=main_menu())
        return

    tv_items    = [x for x in items if x.get('is_tv')]
    movie_items = [x for x in items if not x.get('is_tv')]

    # Determine mode
    if nav_mode == "auto":
        if tv_items and len(tv_items) >= len(movie_items):
            nav_mode = "tv"
            ctx.user_data["nav_mode"] = "tv"
        else:
            nav_mode = "movie"
            ctx.user_data["nav_mode"] = "movie"

    if nav_mode == "tv":
        await show_season_list(update, ctx, msg, tv_items, title)
    elif nav_mode == "season":
        await show_quality_list(update, ctx, msg)
    elif nav_mode == "quality":
        await show_episode_list(update, ctx, msg)
    else:
        await show_movie_list(update, ctx, msg, items if not movie_items else movie_items, title, sort, filter_, page)

async def show_season_list(update, ctx, msg, tv_items: list, title: str):
    """Show seasons selection"""
    seasons = defaultdict(set)
    season_items = defaultdict(list)

    for item in tv_items:
        s = item.get('season')
        if s is None:
            continue
        s_key = str(s)
        eps = item.get('episodes', [])
        if eps:
            if 'pack' in eps:
                seasons[s_key].add('pack')
            else:
                seasons[s_key].update(e for e in eps if e != 'pack')
        else:
            seasons[s_key].add('pack')
        season_items[s_key].append(item)

    ctx.user_data["season_items"] = dict(season_items)
    ctx.user_data["seasons_info"] = {k: list(v) for k, v in seasons.items()}

    sorted_seasons = sorted(seasons.keys(), key=lambda x: int(x) if x.isdigit() else 0, reverse=True)

    kb = []
    text = f"📺 *{escape_md(title)}*\n\n*انتخاب فصل:*\n\n"

    for s in sorted_seasons[:15]:
        eps_set = seasons[s]
        if 'pack' in eps_set:
            count_text = "🗂 Full Season"
        else:
            count_text = f"📝 {len(eps_set)} قسمت"
        torrent_count = len(season_items[s])
        text += f"📚 فصل {s} — {count_text} ({torrent_count} فایل)\n"
        kb.append([InlineKeyboardButton(f"📚 فصل {s} ({count_text})", callback_data=f"season_{s}")])

    if not sorted_seasons:
        # No season info found, fall back to movie list
        ctx.user_data["nav_mode"] = "movie"
        await show_movie_list(update, ctx, msg, tv_items, title, ctx.user_data.get("sort","newest"), ctx.user_data.get("filter_indexer"), 0)
        return

    kb.append([InlineKeyboardButton("📋 نمایش همه نتایج", callback_data="all_raw")])
    kb.append([InlineKeyboardButton("◀️ برگشت", callback_data="back")])

    try:
        await msg.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    except:
        await msg.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

async def show_quality_list(update, ctx, msg):
    """Show quality options for selected season"""
    season       = ctx.user_data.get("current_season", "")
    season_items = ctx.user_data.get("season_items", {})
    episodes     = season_items.get(season, [])
    title        = ctx.user_data.get("search_title", "")

    if not episodes:
        await msg.edit_text("❌ هیچ قسمتی پیدا نشد.", reply_markup=main_menu())
        return

    qualities = defaultdict(list)
    for ep in episodes:
        q = ep.get('quality', 'Unknown')
        qualities[q].append(ep)

    quality_order = {'4K': 0, '2160P': 0, '1080P': 1, '720P': 2, '480P': 3, 'UNKNOWN': 99}
    sorted_q = sorted(qualities.keys(), key=lambda x: quality_order.get(x.upper(), 50))

    ctx.user_data["quality_items"] = dict(qualities)

    kb = []
    text = f"📺 *{escape_md(title)}* — فصل {season}\n\n*انتخاب کیفیت:*\n\n"

    for q in sorted_q:
        count = len(qualities[q])
        # Count unique episodes
        unique_eps = set()
        for ep in qualities[q]:
            if ep.get('episode'):
                unique_eps.add(ep['episode'])
        ep_text = f"{len(unique_eps)} قسمت" if unique_eps else f"{count} فایل"
        text += f"🎬 {q} — {ep_text}\n"
        kb.append([InlineKeyboardButton(f"🎬 {q} ({ep_text})", callback_data=f"quality_{q}")])

    kb.append([InlineKeyboardButton("◀️ برگشت به فصل‌ها", callback_data="back_seasons")])

    try:
        await msg.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    except:
        await msg.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

async def show_episode_list(update, ctx, msg):
    """Show episodes for selected quality"""
    quality      = ctx.user_data.get("current_quality", "")
    quality_items= ctx.user_data.get("quality_items", {})
    episodes     = quality_items.get(quality, [])
    title        = ctx.user_data.get("search_title", "")
    season       = ctx.user_data.get("current_season", "")
    page         = ctx.user_data.get("ep_page", 0)

    if not episodes:
        await msg.edit_text("❌ هیچ قسمتی پیدا نشد.", reply_markup=main_menu())
        return

    # Sort: packs first, then by episode number descending
    packs = [e for e in episodes if e.get('is_pack')]
    eps   = [e for e in episodes if not e.get('is_pack')]
    eps.sort(key=lambda x: x.get('episode', 0) or 0, reverse=True)
    sorted_episodes = packs + eps

    ctx.user_data["episode_list"] = sorted_episodes

    total = max(1, (len(sorted_episodes) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    start = page * ITEMS_PER_PAGE

    kb = []
    text = f"📺 *{escape_md(title)}* — S{season} — {quality}\n\n"

    for i, ep in enumerate(sorted_episodes[start:start + ITEMS_PER_PAGE]):
        ep_num  = ep.get('episode')
        size    = fmt_size(ep.get('Size', '0'))
        seeders = ep.get('Seeders', '0')
        indexer = ep.get('Indexer', 'Unknown')
        is_pack = ep.get('is_pack', False)
        full_title = ep.get('Title', '?')
        
        # Truncate title to fit button (max ~80 chars for display)
        display_title = full_title[:75] + "..." if len(full_title) > 78 else full_title
        
        # First row: Full title (download action)
        title_btn = InlineKeyboardButton(display_title, callback_data=f"dl_ep_{start+i}")
        
        # Second row: Info (no action - just display)
        ep_label = f"🗂 Pack" if is_pack else (f"E{ep_num:02d}" if ep_num else "🎬")
        info_text = f"{ep_label} | 📦 {size} | 👤{seeders} | 🌐 {indexer[:12]}"
        info_btn = InlineKeyboardButton(info_text, callback_data="noop")
        
        kb.append([title_btn])
        kb.append([info_btn])

    kb.extend(paginate_buttons(page, total, "ep"))
    kb.append([InlineKeyboardButton("◀️ برگشت به کیفیت", callback_data="back_quality")])

    try:
        await msg.edit_text(text or "📝 قسمت‌ها:", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    except:
        await msg.reply_text(text or "📝 قسمت‌ها:", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

async def show_movie_list(update, ctx, msg, items: list, title: str, sort: str, filter_: str, page: int):
    """Show flat paginated movie/general results"""
    total_pages = max(1, (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * ITEMS_PER_PAGE

    filter_name = filter_ or "همه"
    caption  = f"🎬 *{escape_md(title)}*\n"
    caption += f"📊 {len(items)} نتیجه | {filter_name} | "
    caption += ("✅🆕 جدید" if sort == "newest" else "✅👤 سید بیشتر") + "\n\n"

    kb = []
    all_indexers = await get_indexers()
    for i, t in enumerate(items[start:start + ITEMS_PER_PAGE]):
        idx_em  = get_indexer_emoji(t.get('Indexer', ''), all_indexers)
        size    = fmt_size(t.get('Size', '0'))
        seeders = t.get('Seeders', '0')
        quality = t.get('quality', '')
        s       = t.get('season')
        ep      = t.get('episode')
        is_pack = t.get('is_pack', False)

        # Build se_info
        if s and ep:
            se_info = f" S{s:02d}E{ep:02d}"
        elif s and is_pack:
            se_info = f" S{s:02d} Pack"
        elif s:
            se_info = f" S{s:02d}"
        else:
            se_info = ""

        q_str = f" [{quality}]" if quality and quality != 'Unknown' else ""
        name  = t.get('Title', '?')
        num   = start + i + 1

        caption += f"{num}. {idx_em}{q_str}{se_info} | {size} | 👤{seeders}\n"
        caption += f"   `{name[:60]}`\n\n"

        kb.append([InlineKeyboardButton(
            f"📥 #{num} {idx_em} {q_str} {size} 👤{seeders}",
            callback_data=f"dl_movie_{start+i}"
        )])

    kb.extend(paginate_buttons(page, total_pages))
    kb.extend(sort_buttons(sort))
    kb.extend(await indexer_buttons(filter_))
    kb.append([InlineKeyboardButton("◀️ برگشت", callback_data="back")])

    # Store flat list for download callbacks
    ctx.user_data["flat_list"] = items
    ctx.user_data["page"] = page

    try:
        await msg.edit_text(caption, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e:
        logger.error(f"show_movie_list edit error: {e}")
        try:
            await msg.reply_text(caption[:4000], parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
        except Exception as e2:
            logger.error(f"show_movie_list reply error: {e2}")

def escape_md(text: str) -> str:
    """Escape special Markdown characters"""
    for ch in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(ch, f'\\{ch}')
    return text

# ─── Command Handlers ─────────────────────────────────────────────────────────

async def start_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await unauthorized_reply(update)
        return
    text = (
        "🌙 *Night Leech Bot* 🦞\n\n"
        "دانلود فیلم و سریال از طریق تورنت\n\n"
        "📖 *راهنما:*\n"
        "• `/search نام فیلم` — جستجوی مستقیم\n"
        "• `@NightLeechBot نام` — جستجو با پیشنهاد IMDB\n"
        "• `/imdb نام` — جستجو با عنوان\n\n"
        "📥 *دانلودها را از منوی پایین ببینید*"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_menu())

async def search_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Direct search command - /search <query>"""
    if not is_authorized(update):
        await unauthorized_reply(update)
        return
    if not update.message or not update.message.text:
        return
    query = update.message.text[8:].strip()  # Remove '/search '
    if not query:
        await update.message.reply_text("❓ مثال: `/search Breaking Bad`", parse_mode='Markdown')
        return
    await _do_search(update, ctx, query)

async def imdb_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Search via /imdb command"""
    if not is_authorized(update):
        await unauthorized_reply(update)
        return
    if not update.message or not update.message.text:
        return
    query = update.message.text[6:].strip()
    if not query:
        await update.message.reply_text("❓ مثال: `/imdb Breaking Bad 2008`", parse_mode='Markdown')
        return
    await _do_search(update, ctx, query)

async def _do_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE, query: str):
    """Core search logic used by both /search and /imdb"""
    ctx.user_data.clear()
    msg = await update.message.reply_text(f"🔍 در حال جستجو: *{query}*...", parse_mode='Markdown')

    try:
        results = await search_jackett(query, sort_by=ctx.user_data.get("sort", "newest"))
    except Exception as e:
        logger.error(f"Search error: {e}")
        results = []

    if not results:
        await msg.edit_text(
            f"❌ نتیجه‌ای برای *{query}* پیدا نشد.\n\nممکن است:\n• ایندکسر آنلاین نباشد\n• نام را به انگلیسی تایپ کنید",
            parse_mode='Markdown',
            reply_markup=main_menu()
        )
        return

    ctx.user_data.update({
        "results":       results,
        "search_title":  query,
        "page":          0,
        "sort":          "newest",
        "filter_indexer": None,
        "nav_mode":      "auto",
    })
    await show_results(update, ctx, msg)

# ─── Inline Query ─────────────────────────────────────────────────────────────

async def inline_query_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()
    if not query or len(query) < 2:
        return

    suggestions = await get_imdb_suggestions(query)
    if not suggestions:
        return

    articles = []
    for i, item in enumerate(suggestions):
        year_str = f" ({item['year']})" if item['year'] else ""
        type_emoji = "📺" if item['type'] in ('TV series', 'TV mini-series') else "🎬"
        articles.append(InlineQueryResultArticle(
            id=str(i),
            title=f"{type_emoji} {item['title']}{year_str}",
            description="لمس کنید تا جستجو شود",
            thumbnail_url=item.get('poster', '') or None,
            input_message_content=InputTextMessageContent(
                message_text=f"/search {item['title']}{year_str}"
            )
        ))
    await update.inline_query.answer(articles, cache_time=300, is_personal=True)

# ─── Callback Handler ─────────────────────────────────────────────────────────

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if not is_authorized(update):
        await query.answer("⛔ دسترسی ندارید", show_alert=True)
        return

    # ── Navigation ──────────────────────────────────────────────
    if data == "back":
        ctx.user_data.clear()
        await query.edit_message_text(
            "🌙 *Night Leech Bot* 🦞\n\n🔍 برای جستجو: `/search نام فیلم`",
            parse_mode='Markdown', reply_markup=main_menu()
        )

    elif data == "noop":
        pass  # pagination label button

    elif data == "back_seasons":
        ctx.user_data["nav_mode"] = "tv"
        ctx.user_data["page"] = 0
        items = ctx.user_data.get("results", [])
        title = ctx.user_data.get("search_title", "")
        tv_items = [x for x in items if x.get('is_tv')]
        await show_season_list(update, ctx, query.message, tv_items, title)

    elif data == "back_quality":
        ctx.user_data["nav_mode"] = "season"
        ctx.user_data["page"] = 0
        await show_quality_list(update, ctx, query.message)

    elif data == "all_raw":
        ctx.user_data["nav_mode"] = "movie"
        ctx.user_data["page"] = 0
        items = ctx.user_data.get("results", [])
        title = ctx.user_data.get("search_title", "")
        sort  = ctx.user_data.get("sort", "newest")
        await show_movie_list(update, ctx, query.message, items, title, sort, None, 0)

    # ── Season Select ────────────────────────────────────────────
    elif data.startswith("season_"):
        season = data[7:]
        ctx.user_data["current_season"] = season
        ctx.user_data["nav_mode"] = "season"
        ctx.user_data["page"] = 0
        await show_quality_list(update, ctx, query.message)

    # ── Quality Select ───────────────────────────────────────────
    elif data.startswith("quality_"):
        quality = data[8:]
        ctx.user_data["current_quality"] = quality
        ctx.user_data["nav_mode"] = "quality"
        ctx.user_data["ep_page"] = 0
        await show_episode_list(update, ctx, query.message)

    # ── Episode pagination ────────────────────────────────────────
    elif data.startswith("ep_"):
        ctx.user_data["ep_page"] = int(data[3:])
        await show_episode_list(update, ctx, query.message)

    # ── Download Episode ─────────────────────────────────────────
    elif data.startswith("dl_ep_"):
        idx = int(data[6:])
        episodes = ctx.user_data.get("episode_list", [])
        if idx < len(episodes):
            t = episodes[idx]
            magnet = t.get("Magnet", "")
            await _add_torrent(query, t, magnet)
        else:
            await query.edit_message_text("❌ آیتم پیدا نشد.", reply_markup=main_menu())

    # ── Download Movie ────────────────────────────────────────────
    elif data.startswith("dl_movie_"):
        idx = int(data[9:])
        flat = ctx.user_data.get("flat_list", [])
        if idx < len(flat):
            t = flat[idx]
            magnet = t.get("Magnet", "")
            await _add_torrent(query, t, magnet)
        else:
            await query.edit_message_text("❌ آیتم پیدا نشد.", reply_markup=main_menu())

    # ── Sort ──────────────────────────────────────────────────────
    elif data.startswith("sort_"):
        sort = data[5:]  # 'seeders' or 'newest'
        ctx.user_data["sort"] = sort
        ctx.user_data["page"] = 0
        # Re-sort existing results
        items = ctx.user_data.get("results", [])
        if sort == "seeders":
            items.sort(key=lambda x: int(x.get('Seeders', 0)), reverse=True)
        else:
            items.sort(key=lambda x: x.get('ParsedDate', datetime.min), reverse=True)
        ctx.user_data["results"] = items
        ctx.user_data["nav_mode"] = "movie"
        title = ctx.user_data.get("search_title", "")
        await show_movie_list(update, ctx, query.message, items, title, sort, ctx.user_data.get("filter_indexer"), 0)

    # ── Indexer Filter ────────────────────────────────────────────
    elif data.startswith("idx_"):
        filter_idx = None if data == "idx_all" else data[4:]
        ctx.user_data["filter_indexer"] = filter_idx
        ctx.user_data["page"] = 0
        title = ctx.user_data.get("search_title", "")
        sort  = ctx.user_data.get("sort", "newest")
        # Re-filter from all results
        all_results = ctx.user_data.get("results", [])
        filtered = [x for x in all_results if x.get('Indexer') == filter_idx] if filter_idx else all_results
        ctx.user_data["nav_mode"] = "movie"
        await show_movie_list(update, ctx, query.message, filtered, title, sort, filter_idx, 0)

    # ── Pagination ────────────────────────────────────────────────
    elif data.startswith("p_"):
        ctx.user_data["page"] = int(data[2:])
        items = ctx.user_data.get("flat_list", ctx.user_data.get("results", []))
        title = ctx.user_data.get("search_title", "")
        sort  = ctx.user_data.get("sort", "newest")
        filter_ = ctx.user_data.get("filter_indexer")
        await show_movie_list(update, ctx, query.message, items, title, sort, filter_, ctx.user_data["page"])

    # ── Downloads List ────────────────────────────────────────────
    elif data == "downloads":
        await show_downloads(query)

    # ── Download Detail ───────────────────────────────────────────
    elif data.startswith("dlt_"):
        h = data[4:]
        await show_torrent_detail(query, h)

    # ── Delete Torrent ────────────────────────────────────────────
    elif data.startswith("del_"):
        h = data[4:]
        success = await qbit_delete(h)
        if success:
            await query.edit_message_text("✅ حذف شد!", reply_markup=main_menu())
        else:
            await query.edit_message_text("❌ خطا در حذف.", reply_markup=main_menu())

    # ── Status ────────────────────────────────────────────────────
    elif data == "status":
        await show_status(query)

async def _add_torrent(query, torrent_info: dict, magnet: str):
    """Add a torrent magnet or .torrent URL to qBittorrent"""
    title   = torrent_info.get('Title', '?')
    size    = fmt_size(torrent_info.get('Size', '0'))
    seeders = torrent_info.get('Seeders', '0')

    # Check if it's a magnet link or a .torrent URL
    is_magnet = magnet.startswith('magnet:')
    is_torrent_url = magnet.startswith('http') and ('.torrent' in magnet or '/dl/' in magnet or 'jackett' in magnet)
    
    if not magnet or (not is_magnet and not is_torrent_url):
        await query.edit_message_text(
            f"❌ مگنت لینک پیدا نشد!\n\n`{title[:60]}`\n\nاین نتیجه لینک مگنت معتبر ندارد.",
            parse_mode='Markdown', reply_markup=main_menu()
        )
        return

    success = await qbit_add_magnet(magnet)
    if success:
        await query.edit_message_text(
            f"✅ *اضافه شد!*\n\n🎬 `{title[:60]}`\n📦 {size} | 👤 {seeders} seeders",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 مشاهده دانلودها", callback_data="downloads")],
                [InlineKeyboardButton("◀️ برگشت", callback_data="back")],
            ])
        )
    else:
        await query.edit_message_text(
            "❌ خطا در اضافه کردن تورنت.\nممکن است qBittorrent آنلاین نباشد.",
            reply_markup=main_menu()
        )

async def show_downloads(msg):
    """Show active downloads list"""
    torrents = await qbit_get_torrents()
    if not torrents:
        await msg.edit_message_text("📥 دانلودی وجود ندارد.", reply_markup=main_menu())
        return

    kb = []
    for t in torrents[:15]:
        name     = t.get('name', '?')[:28]
        progress = t.get('progress', 0) * 100
        bar      = "█" * int(progress / 10) + "░" * (10 - int(progress / 10))
        state    = t.get('state', '')
        if state in ('downloading', 'stalledDL'):
            emoji = "⬇️"
        elif state == 'uploading':
            emoji = "⬆️"
        elif state == 'pausedDL':
            emoji = "⏸️"
        else:
            emoji = "✅"
        kb.append([InlineKeyboardButton(
            f"{emoji} {name} {progress:.0f}%",
            callback_data=f"dlt_{t.get('hash','')}"
        )])

    kb.extend([
        [InlineKeyboardButton("🔄 رفرش", callback_data="downloads")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="back")]
    ])
    await msg.edit_message_text(
        f"📥 *دانلودها* ({len(torrents)}):",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def show_torrent_detail(msg, hash_: str):
    """Show details for a specific torrent"""
    torrents = await qbit_get_torrents()
    t = next((x for x in torrents if x.get('hash') == hash_), None)
    if not t:
        await msg.edit_message_text("❌ تورنت پیدا نشد.", reply_markup=main_menu())
        return

    progress = t.get('progress', 0) * 100
    bar      = "█" * int(progress / 10) + "░" * (10 - int(progress / 10))
    name     = t.get('name', '?')
    state    = t.get('state', '?')
    dl_speed = fmt_size(t.get('dlspeed', 0))
    ul_speed = fmt_size(t.get('upspeed', 0))
    size_done= fmt_size(t.get('downloaded', 0))
    size_tot = fmt_size(t.get('size', 0))

    info = (
        f"🎬 `{name[:55]}`\n\n"
        f"📊 {bar} {progress:.1f}%\n"
        f"📦 {size_done} / {size_tot}\n"
        f"⬇️ {dl_speed}/s | ⬆️ {ul_speed}/s\n"
        f"🔰 {state}"
    )

    # FIX: Only show download link when fully complete (100%)
    if progress >= 99.9:
        files = await qbit_get_files(hash_)
        if files:
            # Get the largest file (usually the video)
            video_exts = {'.mkv', '.mp4', '.avi', '.mov', '.wmv'}
            video_files = [f for f in files if any(f.get('name','').lower().endswith(ext) for ext in video_exts)]
            target_file = max(video_files, key=lambda f: f.get('size', 0)) if video_files else files[0]
            fn = target_file.get('name', name)
            info += f"\n\n🔗 [دانلود فایل]({FILE_SERVER_URL}/download/{fn})"

    kb = [
        [InlineKeyboardButton("🗑️ حذف", callback_data=f"del_{hash_}")],
        [InlineKeyboardButton("🔄 رفرش", callback_data=f"dlt_{hash_}")],
        [InlineKeyboardButton("◀️ برگشت", callback_data="downloads")],
    ]
    await msg.edit_message_text(info, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

async def show_status(msg):
    """Show bot and qBit status"""
    torrents    = await qbit_get_torrents()
    active      = sum(1 for t in torrents if t.get('state') in ('downloading', 'stalledDL'))
    seeding     = sum(1 for t in torrents if t.get('state') == 'uploading')
    total_size  = sum(t.get('size', 0) for t in torrents)
    dl_total    = sum(t.get('downloaded', 0) for t in torrents)

    all_indexers = await get_indexers()
    indexer_names = ', '.join(x[0] for x in all_indexers) if all_indexers else "در حال بارگذاری..."
    
    text = (
        f"⚙️ *وضعیت ربات*\n\n"
        f"✅ ربات: آنلاین\n"
        f"📥 تورنت‌ها: {len(torrents)}\n"
        f"⬇️ در حال دانلود: {active}\n"
        f"⬆️ سیدینگ: {seeding}\n"
        f"💾 حجم کل: {fmt_size(total_size)}\n"
        f"📦 دانلود شده: {fmt_size(dl_total)}\n\n"
        f"🔍 ایندکسرها: {indexer_names}"
    )
    await msg.edit_message_text(text, parse_mode='Markdown', reply_markup=main_menu())

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await unauthorized_reply(update)
        return
    # Treat any text message as a search query
    text = update.message.text.strip() if update.message and update.message.text else ""
    if text and not text.startswith('/'):
        await _do_search(update, ctx, text)
    else:
        await update.message.reply_text(
            "🌙 *Night Leech Bot* 🦞\n\n"
            "🔍 برای جستجو یک نام فیلم/سریال بنویس یا از `/search` استفاده کن.",
            parse_mode='Markdown',
            reply_markup=main_menu()
        )

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set! Edit config.env")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",  start_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("imdb",   imdb_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(InlineQueryHandler(inline_query_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("🌙 Night Leech Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
