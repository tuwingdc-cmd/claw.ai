"""
Message Handler + DB-backed Conversation Memory + Smart Skills + Tools + Music + URL Fetch
"""
import json
import math
import logging
import re
import asyncio
import aiohttp
import os
import tempfile
from typing import Dict, List, Optional
from datetime import datetime
from core.providers import ProviderFactory, AIResponse
from core.database import (
    save_message, get_conversation, clear_conversation,
    get_memory_stats, MAX_MEMORY_MESSAGES
)
from config import API_KEYS, FALLBACK_CHAINS, PROVIDERS

log = logging.getLogger(__name__)

# Re-export for backward compatibility
MEMORY_EXPIRE_MINUTES = 0

# ============================================================
# REQUEST LOGS
# ============================================================

request_logs: List[Dict] = []
MAX_LOGS = 500

def _log_request(guild_id, provider, model, success, latency, is_fallback=False, error=None):
    request_logs.append({"guild_id": guild_id, "provider": provider, "model": model, "success": success, "latency": latency, "is_fallback": is_fallback, "error": error, "time": datetime.now().strftime("%H:%M:%S")})
    if len(request_logs) > MAX_LOGS:
        request_logs.pop(0)

def strip_think_tags(content: str) -> str:
    for tag in ['think', 'thinking', 'thought']:
        content = re.sub(rf'<{tag}>.*?</{tag}>', '', content, flags=re.DOTALL)
        content = re.sub(rf'</?{tag}>', '', content)
    return re.sub(r'\n{3,}', '\n\n', content).strip()

# ============================================================
# SEARCH — Tavily first, DuckDuckGo fallback
# ============================================================

async def do_search(query: str, engine: str = "auto") -> str:
    tavily_key = API_KEYS.get("tavily")
    if tavily_key:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": tavily_key,
                        "query": query,
                        "max_results": 5,
                        "search_depth": "basic",
                        "include_answer": True,
                    },
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        parts = []
                        if data.get("answer"):
                            parts.append(f"Summary: {data['answer']}")
                        for i, r in enumerate(data.get("results", []), 1):
                            parts.append(
                                f"{i}. {r.get('title', 'No title')}\n"
                                f"   {r.get('content', '')[:200]}\n"
                                f"   {r.get('url', '')}"
                            )
                        if parts:
                            log.info(f"🔍 Tavily search OK: {query}")
                            return "\n\n".join(parts)
                    else:
                        log.warning(f"Tavily HTTP {resp.status}, fallback to DuckDuckGo")
        except Exception as e:
            log.warning(f"Tavily error, fallback to DuckDuckGo: {e}")

    try:
        from duckduckgo_search import DDGS
        def _s():
            with DDGS() as d:
                return list(d.text(query, max_results=5))
        results = await asyncio.get_event_loop().run_in_executor(None, _s)
        if not results:
            return "Tidak ada hasil."
        log.info(f"🔍 DuckDuckGo search OK: {query}")
        return "\n\n".join([
            f"{i}. {r['title']}\n   {r['body'][:150]}\n   {r['href']}"
            for i, r in enumerate(results, 1)
        ])
    except Exception as e:
        return f"Search error: {e}"

GROUNDING_MODELS = {("groq", "groq/compound"), ("groq", "groq/compound-mini"), ("groq", "compound-beta"), ("groq", "compound-beta-mini"), ("pollinations", "gemini-search"), ("pollinations", "perplexity-fast"), ("pollinations", "perplexity-reasoning")}
def is_grounding_model(p, m): return (p, m) in GROUNDING_MODELS

# ============================================================
# TRANSLATE — AI-powered natural translation
# ============================================================

async def do_translate(text: str, target_lang: str, style: str = "natural") -> str:
    style_prompts = {
        "natural": (
            "You are a native bilingual translator. Translate naturally as a native speaker would say it. "
            "Understand slang, idioms, colloquialisms, and cultural context. "
            "Do NOT translate literally word-by-word. Make it sound like something a real person would say. "
            "Only output the translation, nothing else."
        ),
        "formal": (
            "You are a professional translator. Translate in formal, polished language. "
            "Only output the translation, nothing else."
        ),
        "casual": (
            "You are a young native speaker. Translate super casually with modern slang and abbreviations. "
            "Make it sound like texting a friend. Only output the translation, nothing else."
        ),
    }

    system_prompt = style_prompts.get(style, style_prompts["natural"])
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Translate to {target_lang}:\n\n{text}"}
    ]

    translate_chains = [
        ("groq", "llama-3.1-8b-instant"),
        ("groq", "llama-3.3-70b-versatile"),
        ("cerebras", "llama3.1-8b"),
        ("sambanova", "Meta-Llama-3.1-8B-Instruct"),
        ("pollinations", "openai-fast"),
    ]

    for prov_name, model_id in translate_chains:
        prov = ProviderFactory.get(prov_name, API_KEYS)
        if not prov or not await prov.health_check():
            continue
        try:
            resp = await prov.chat(messages, model_id, temperature=0.3, max_tokens=2048)
            if resp.success and resp.content.strip():
                log.info(f"🌐 Translated via {prov_name}/{model_id}")
                return resp.content.strip()
        except Exception as e:
            log.warning(f"Translate error {prov_name}: {e}")
            continue

    return f"[Translation failed] {text}"

# ============================================================
# URL FETCH — Universal URL Reader
# ============================================================

def _detect_platform(url: str) -> str:
    """Detect platform from URL"""
    url_lower = url.lower()
    if "twitter.com" in url_lower or "x.com" in url_lower:
        return "twitter"
    elif "instagram.com" in url_lower:
        return "instagram"
    elif "tiktok.com" in url_lower:
        return "tiktok"
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    elif "reddit.com" in url_lower:
        return "reddit"
    elif "github.com" in url_lower:
        return "github"
    return "generic"

def _extract_youtube_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL"""
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:shorts/)([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

async def _fetch_via_jina(url: str) -> Optional[str]:
    """Fetch URL content via Jina Reader — works for most websites"""
    try:
        jina_url = f"https://r.jina.ai/{url}"
        headers = {
            "Accept": "text/markdown",
            "User-Agent": "Mozilla/5.0 (compatible; DiscordBot/1.0)"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                jina_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    # Trim to reasonable size for AI
                    if len(content) > 8000:
                        content = content[:8000] + "\n\n[... content trimmed ...]"
                    log.info(f"📄 Jina Reader OK: {url[:60]}")
                    return content
                else:
                    log.warning(f"📄 Jina Reader HTTP {resp.status} for {url[:60]}")
    except Exception as e:
        log.warning(f"📄 Jina Reader error: {e}")
    return None

async def _fetch_via_bs4(url: str) -> Optional[str]:
    """Fallback: fetch with requests + BeautifulSoup"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("beautifulsoup4 not installed")
        return None
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=True
            ) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")
                    
                    # Remove script, style, nav, footer
                    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
                        tag.decompose()
                    
                    # Try article content first
                    article = soup.find("article")
                    if article:
                        text = article.get_text(separator="\n", strip=True)
                    else:
                        # Fallback to main or body
                        main = soup.find("main") or soup.find("body")
                        text = main.get_text(separator="\n", strip=True) if main else ""
                    
                    # Clean up
                    lines = [line.strip() for line in text.split("\n") if line.strip()]
                    text = "\n".join(lines)
                    
                    if len(text) > 6000:
                        text = text[:6000] + "\n\n[... content trimmed ...]"
                    
                    if len(text) > 100:
                        log.info(f"📄 BS4 fetch OK: {url[:60]}")
                        return text
    except Exception as e:
        log.warning(f"📄 BS4 error: {e}")
    return None

async def _fetch_twitter(url: str) -> Optional[str]:
    """Fetch Twitter/X content via Nitter proxies or Jina"""
    nitter_instances = [
        "nitter.net",
        "nitter.privacydev.net",
        "nitter.poast.org",
    ]
    
    # Extract tweet path
    match = re.search(r'(?:twitter\.com|x\.com)/(\w+)/status/(\d+)', url)
    if not match:
        return await _fetch_via_jina(url)
    
    username, tweet_id = match.group(1), match.group(2)
    
    # Try Nitter instances
    for instance in nitter_instances:
        try:
            nitter_url = f"https://{instance}/{username}/status/{tweet_id}"
            content = await _fetch_via_jina(nitter_url)
            if content and len(content) > 50:
                return f"[Tweet from @{username}]\n\n{content}"
        except:
            continue
    
    # Fallback to direct Jina on original URL
    content = await _fetch_via_jina(url)
    if content:
        return f"[Tweet from @{username}]\n\n{content}"
    
    return None

async def _fetch_youtube_transcript(url: str) -> Optional[str]:
    """Fetch YouTube video info + transcript"""
    video_id = _extract_youtube_id(url)
    if not video_id:
        return None
    
    parts = []
    
    # Step 1: Get video info via oembed (always works)
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        async with aiohttp.ClientSession() as session:
            async with session.get(oembed_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    parts.append(f"Title: {data.get('title', 'Unknown')}")
                    parts.append(f"Channel: {data.get('author_name', 'Unknown')}")
    except:
        pass
    
    # Step 2: Try to get transcript via yt-dlp
    try:
        import yt_dlp
        
        def _get_info():
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "writeautomaticsub": True,
                "subtitleslangs": ["id", "en"],
                "subtitlesformat": "json3",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        info = await asyncio.get_event_loop().run_in_executor(None, _get_info)
        
        if info:
            if not parts:
                parts.append(f"Title: {info.get('title', 'Unknown')}")
                parts.append(f"Channel: {info.get('channel', info.get('uploader', 'Unknown'))}")
            
            duration = info.get("duration", 0)
            if duration:
                mins, secs = divmod(duration, 60)
                parts.append(f"Duration: {int(mins)}:{int(secs):02d}")
            
            view_count = info.get("view_count")
            if view_count:
                parts.append(f"Views: {view_count:,}")
            
            desc = info.get("description", "")
            if desc:
                parts.append(f"Description: {desc[:500]}")
            
            # Get subtitles/transcript
            subtitles = info.get("subtitles", {})
            auto_subs = info.get("automatic_captions", {})
            
            transcript_text = None
            
            # Try manual subs first, then auto
            for sub_source in [subtitles, auto_subs]:
                for lang in ["id", "en"]:
                    if lang in sub_source:
                        for fmt in sub_source[lang]:
                            if fmt.get("ext") == "json3":
                                try:
                                    sub_url = fmt["url"]
                                    async with aiohttp.ClientSession() as session:
                                        async with session.get(sub_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                                            if resp.status == 200:
                                                sub_data = await resp.json()
                                                events = sub_data.get("events", [])
                                                words = []
                                                for event in events:
                                                    segs = event.get("segs", [])
                                                    for seg in segs:
                                                        w = seg.get("utf8", "").strip()
                                                        if w and w != "\n":
                                                            words.append(w)
                                                transcript_text = " ".join(words)
                                except:
                                    pass
                        if transcript_text:
                            break
                if transcript_text:
                    break
            
            if transcript_text:
                if len(transcript_text) > 5000:
                    transcript_text = transcript_text[:5000] + "... [trimmed]"
                parts.append(f"\nTranscript:\n{transcript_text}")
            
            log.info(f"🎬 YouTube info OK: {video_id}")
            return "\n".join(parts)
    
    except ImportError:
        log.warning("yt-dlp not installed, falling back to Jina")
    except Exception as e:
        log.warning(f"yt-dlp error: {e}")
    
    # Fallback to Jina
    jina_content = await _fetch_via_jina(url)
    if jina_content:
        if parts:
            return "\n".join(parts) + "\n\n" + jina_content
        return jina_content
    
    return "\n".join(parts) if parts else None

async def _get_video_download_url(url: str) -> Optional[dict]:
    """Download video langsung pakai yt-dlp — no third-party API needed"""
    try:
        import yt_dlp
        
        def _download_direct():
            temp_dir = tempfile.mkdtemp()
            output_path = os.path.join(temp_dir, "video.mp4")
            
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "format": "best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best",
                "outtmpl": output_path,
                "merge_output_format": "mp4",
                "socket_timeout": 30,
                "retries": 3,
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Find actual downloaded file
                actual_path = output_path
                if not os.path.exists(actual_path):
                    for f in os.listdir(temp_dir):
                        actual_path = os.path.join(temp_dir, f)
                        break
                
                title = info.get("title", "video")[:50]
                clean_title = re.sub(r'[^\w\s-]', '', title).strip()
                clean_title = re.sub(r'\s+', '_', clean_title) or "video"
                
                return {
                    "local_path": actual_path,
                    "temp_dir": temp_dir,
                    "filename": f"{clean_title}.mp4",
                    "status": "local",
                    "filesize": os.path.getsize(actual_path) if os.path.exists(actual_path) else 0,
                    "title": info.get("title", ""),
                    "uploader": info.get("uploader", info.get("channel", "")),
                    "duration": info.get("duration", 0),
                }
        
        result = await asyncio.get_event_loop().run_in_executor(None, _download_direct)
        if result and result.get("local_path") and os.path.exists(result["local_path"]):
            log.info(f"🎬 yt-dlp OK: {result['filename']} ({result.get('filesize', 0) / 1_000_000:.1f}MB)")
            return result
    
    except ImportError:
        log.error("yt-dlp not installed! pip install yt-dlp")
    except Exception as e:
        log.warning(f"yt-dlp error: {e}")
    
    return None

async def do_fetch_url(url: str, action: str = "read") -> str:
    """Universal URL fetcher — read content or get download URL"""
    platform = _detect_platform(url)
    
    log.info(f"📄 Fetching URL: {url[:80]} | platform={platform} | action={action}")
    
        # ── DOWNLOAD ACTION ──
    if action == "download":
        download_info = await _get_video_download_url(url)
        if download_info and download_info.get("status") == "local":
            return json.dumps({
                "type": "download",
                "local_path": download_info["local_path"],
                "temp_dir": download_info["temp_dir"],
                "filename": download_info.get("filename", "video.mp4"),
                "platform": platform,
                "original_url": url,
                "method": "local",
                "title": download_info.get("title", ""),
                "uploader": download_info.get("uploader", ""),
            })
        return "Cannot download video from this URL. The content might be protected, require login, or not a video."
    
    # ── READ/SUMMARIZE ACTION ──
    content = None
    
    if platform == "twitter":
        content = await _fetch_twitter(url)
    
    elif platform == "youtube":
        content = await _fetch_youtube_transcript(url)
    
    elif platform in ("tiktok", "instagram", "reddit"):
        # Try Jina first for metadata
        content = await _fetch_via_jina(url)
    
    elif platform == "github":
        content = await _fetch_via_jina(url)
    
    # Generic / fallback
    if not content:
        content = await _fetch_via_jina(url)
    
    if not content:
        content = await _fetch_via_bs4(url)
    
    if not content:
        return (
            f"Cannot access content from {url}. "
            f"Possible reasons: website requires login, anti-bot protection, "
            f"or content is not publicly accessible."
        )
    
    return f"[Content from {platform}: {url}]\n\n{content}"


# ============================================================
# TOOL DEFINITIONS (8 Tools)
# ============================================================

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the internet for real-time information. "
            "Use this when asked about: current events, news, prices, "
            "who is president/leader/CEO, sports results, "
            "anything that might have changed recently, or any fact "
            "you are not confident about."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query in the most relevant language"}
            },
            "required": ["query"]
        }
    }
}

GET_TIME_TOOL = {
    "type": "function",
    "function": {
        "name": "get_time",
        "description": (
            "Get current date and time in a specific timezone. "
            "Use for questions about: what time is it, today's date, "
            "what day is it, current time in a city/country."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Timezone like Asia/Jakarta, America/New_York, Europe/London, Asia/Tokyo. Default: Asia/Jakarta"
                }
            },
            "required": []
        }
    }
}

GET_WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": (
            "Get current weather for a city. "
            "Use when asked about weather, temperature, rain, humidity in a location."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, e.g. Jakarta, Tokyo, London, New York"
                }
            },
            "required": ["city"]
        }
    }
}

CALCULATE_TOOL = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": (
            "Perform mathematical calculations. "
            "Use for math questions, unit conversions, percentages, etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression like '5 + 3 * 2', 'sqrt(144)', '15% of 200', '2**10'"
                }
            },
            "required": ["expression"]
        }
    }
}

TRANSLATE_TOOL = {
    "type": "function",
    "function": {
        "name": "translate",
        "description": (
            "Translate text between languages naturally like a native speaker. "
            "Understands slang, idioms, and cultural context. "
            "Use when user asks to translate something, or wants to know how to say something in another language."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to translate"},
                "target_language": {"type": "string", "description": "Target language, e.g. English, Indonesian, Japanese, Korean, Spanish"},
                "style": {
                    "type": "string",
                    "enum": ["natural", "formal", "casual"],
                    "description": "Translation style. natural=everyday speech, formal=polished, casual=slang/texting. Default: natural"
                }
            },
            "required": ["text", "target_language"]
        }
    }
}

PLAY_MUSIC_TOOL = {
    "type": "function",
    "function": {
        "name": "play_music",
        "description": (
            "Control music playback in Discord voice channel. "
            "Use when user wants to: play a song, skip track, stop/disconnect music, "
            "pause, or resume playback. "
            "If user is NOT in a voice channel, tell them to join one first."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["play", "skip", "stop", "pause", "resume"],
                    "description": "Music action"
                },
                "query": {
                    "type": "string",
                    "description": "Song name, artist, or URL. Required for 'play' action."
                }
            },
            "required": ["action"]
        }
    }
}

FETCH_URL_TOOL = {
    "type": "function",
    "function": {
        "name": "fetch_url",
        "description": (
            "Read, summarize, or download content from ANY URL. "
            "\n\n"
            "SUPPORTED PLATFORMS FOR DOWNLOAD (video/audio):\n"
            "• TikTok (no watermark)\n"
            "• Instagram (reels, posts, stories, IGTV)\n"
            "• YouTube (videos, shorts, music)\n"
            "• Twitter/X (videos, GIFs)\n"
            "• Facebook (videos, reels)\n"
            "• Reddit (videos)\n"
            "• Pinterest\n"
            "• Twitch (clips)\n"
            "• SoundCloud\n"
            "• Spotify (preview only)\n"
            "• And 1000+ other sites\n"
            "\n"
            "SUPPORTED FOR READING/SUMMARIZING:\n"
            "• News articles, blogs, Medium\n"
            "• Twitter/X tweets\n"
            "• YouTube (title, description, transcript)\n"
            "• GitHub (README, code)\n"
            "• Any website\n"
            "\n"
            "ACTIONS:\n"
            "• action='download' → Download video/audio file\n"
            "• action='read' → Read content\n"
            "• action='summarize' → Read for summarization\n"
            "\n"
            "IMPORTANT: You CAN download from Instagram, TikTok, YouTube, Twitter, etc. "
            "Do NOT say any platform is unsupported — try it first!"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to fetch"
                },
                "action": {
                    "type": "string",
                    "enum": ["read", "summarize", "download"],
                    "description": "read=get content, summarize=for AI summary, download=get video/audio file"
                }
            },
            "required": ["url"]
        }
    }
}

GENERATE_IMAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_image",
        "description": (
            "Generate an image from text description using AI. "
            "Use when user asks to: create/generate/make/draw an image, picture, photo, artwork. "
            "Describe the image in English for best results."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Image description in English. Be detailed for better results. Example: 'a cute cat wearing astronaut suit floating in space, digital art, high quality'"
                },
                "size": {
                    "type": "string",
                    "enum": ["square", "wide", "tall"],
                    "description": "Image aspect ratio. square=1:1, wide=16:9, tall=9:16. Default: square"
                }
            },
            "required": ["prompt"]
        }
    }
}

TOOLS_LIST = [
    WEB_SEARCH_TOOL, GET_TIME_TOOL, GET_WEATHER_TOOL, CALCULATE_TOOL,
    TRANSLATE_TOOL, PLAY_MUSIC_TOOL, FETCH_URL_TOOL, GENERATE_IMAGE_TOOL
]


# ============================================================
# MODE DETECTOR
# ============================================================

class ModeDetector:
    SEARCH_KW = ["berita terbaru", "harga sekarang", "news today", "current price", "latest news"]
    REASON_KW = ["jelaskan step by step", "hitung ", "analisis ", "solve ", "tulis kode", "write code"]
    
    @classmethod
    def detect(cls, content):
        lower = content.lower()
        for kw in cls.SEARCH_KW:
            if kw in lower: return "search"
        for kw in cls.REASON_KW:
            if kw in lower: return "reasoning"
        return "normal"


# ============================================================
# TOOL CALL EXECUTOR — 8 Tools
# ============================================================

async def execute_tool_call(tool_name: str, tool_args: dict) -> str:
    """Eksekusi tool yang diminta AI"""

    # ── WEB SEARCH ──
    if tool_name == "web_search":
        query = tool_args.get("query", "")
        log.info(f"🔍 Tool: web_search({query})")
        return await do_search(query)

    # ── GET TIME ──
    elif tool_name == "get_time":
        from skills.time_skill import get_current_time
        tz = tool_args.get("timezone", "Asia/Jakarta")
        log.info(f"🕐 Tool: get_time({tz})")
        result = get_current_time(tz)
        if result["success"]:
            return f"Current time in {tz}: {result['full']}"
        return f"Error: {result.get('error', 'Unknown timezone')}"

    # ── GET WEATHER ──
    elif tool_name == "get_weather":
        from skills.weather_skill import get_weather
        city = tool_args.get("city", "Jakarta")
        log.info(f"🌤️ Tool: get_weather({city})")
        result = await get_weather(city)
        if result["success"]:
            return (
                f"Weather in {result['city']}: {result['description']}, "
                f"Temperature: {result['temp']}°C (feels like {result['feels_like']}°C), "
                f"Humidity: {result['humidity']}%, "
                f"Wind: {result['wind_speed']} km/h"
            )
        return f"Error: {result.get('error', 'City not found')}"

    # ── CALCULATE ──
    elif tool_name == "calculate":
        expression = tool_args.get("expression", "")
        log.info(f"🔢 Tool: calculate({expression})")
        try:
            expr = expression.replace("^", "**").replace("×", "*").replace("÷", "/")
            pct_match = re.match(r'([\d.]+)%\s*of\s*([\d.]+)', expr, re.IGNORECASE)
            if pct_match:
                pct, val = float(pct_match.group(1)), float(pct_match.group(2))
                result = pct / 100 * val
                return f"{expression} = {result}"
            allowed = {
                "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
                "tan": math.tan, "log": math.log, "log10": math.log10,
                "log2": math.log2, "ceil": math.ceil, "floor": math.floor,
                "abs": abs, "round": round, "pow": pow, "max": max, "min": min,
                "pi": math.pi, "e": math.e,
            }
            result = eval(expr, {"__builtins__": {}}, allowed)
            return f"{expression} = {result}"
        except Exception as e:
            return f"Calculation error: {e}"

    # ── TRANSLATE ──
    elif tool_name == "translate":
        text = tool_args.get("text", "")
        target = tool_args.get("target_language", "English")
        style = tool_args.get("style", "natural")
        log.info(f"🌐 Tool: translate(→{target}, style={style})")
        return await do_translate(text, target, style)

    # ── PLAY MUSIC ──
    elif tool_name == "play_music":
        action = tool_args.get("action", "play")
        query = tool_args.get("query", "")
        log.info(f"🎵 Tool: play_music(action={action}, query={query})")
        if action == "play":
            return f"Music command accepted. Now playing '{query}' in the user's voice channel."
        elif action == "skip":
            return "Skipping to the next track."
        elif action == "stop":
            return "Stopping music and disconnecting from voice channel."
        elif action == "pause":
            return "Pausing current track."
        elif action == "resume":
            return "Resuming playback."
        return f"Music action '{action}' accepted."

    # ── FETCH URL ──
    elif tool_name == "fetch_url":
        url = tool_args.get("url", "")
        action = tool_args.get("action", "read")
        log.info(f"📄 Tool: fetch_url({url[:60]}, action={action})")
        return await do_fetch_url(url, action)

    # ── GENERATE IMAGE ──
    elif tool_name == "generate_image":
        prompt = tool_args.get("prompt", "")
        size = tool_args.get("size", "square")
        log.info(f"🖼️ Tool: generate_image(prompt={prompt[:50]}, size={size})")
        
        size_map = {
            "square": (1024, 1024),
            "wide": (1280, 720),
            "tall": (720, 1280),
        }
        w, h = size_map.get(size, (1024, 1024))
        
        # Pollinations free image generation
        image_url = f"https://image.pollinations.ai/prompt/{prompt}?width={w}&height={h}&nologo=true&seed={int(datetime.now().timestamp())}"
        
        return json.dumps({
            "type": "image",
            "image_url": image_url,
            "prompt": prompt,
            "size": size,
        })

    return f"Unknown tool: {tool_name}"


# ============================================================
# TOOL CALLING HANDLER
# ============================================================

async def handle_with_tools(messages: list, prov_name: str, model: str,
                             guild_id: int = 0) -> tuple:
    """
    Returns: (AIResponse, note_string, actions_list)
    """
    from core.providers import supports_tool_calling

    if not supports_tool_calling(prov_name):
        return None, None, []

    prov = ProviderFactory.get(prov_name, API_KEYS)
    if not prov or not await prov.health_check():
        return None, None, []

    log.info(f"🤖 Tool calling: {prov_name}/{model}")
    resp = await prov.chat(messages, model, tools=TOOLS_LIST, tool_choice="auto")

    if not resp.success:
        return None, None, []

    tool_calls = getattr(resp, "tool_calls", None)
    if not tool_calls:
        return resp, None, []

    max_rounds = 3
    current_messages = list(messages)
    tools_used = []
    pending_actions = []  # music, download, image

    for round_num in range(max_rounds):
        current_messages.append({
            "role": "assistant",
            "content": resp.content or "",
            "tool_calls": tool_calls
        })

        for tc in tool_calls:
            fn_name = tc.get("function", {}).get("name", "")
            fn_args_str = tc.get("function", {}).get("arguments", "{}")
            tool_call_id = tc.get("id", f"call_{round_num}")

            try:
                fn_args = json.loads(fn_args_str)
            except (json.JSONDecodeError, TypeError):
                fn_args = {"query": fn_args_str}

            # Capture actions BEFORE executing
            if fn_name == "play_music":
                pending_actions.append({
                    "type": "music",
                    "action": fn_args.get("action", "play"),
                    "query": fn_args.get("query", ""),
                })

            tool_result = await execute_tool_call(fn_name, fn_args)
            
            # Check if tool returned a structured action (download, image)
            try:
                result_data = json.loads(tool_result)
                if isinstance(result_data, dict) and result_data.get("type") == "download":
                    pending_actions.append(result_data)
                elif isinstance(result_data, dict) and result_data.get("type") == "image":
                    pending_actions.append(result_data)
            except (json.JSONDecodeError, TypeError):
                pass
            
            log.info(f"✅ Round {round_num + 1}: {fn_name}")
            tools_used.append(fn_name)

            current_messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": tool_result if not tool_result.startswith("{") else f"Result: {tool_result}"
            })

        resp = await prov.chat(current_messages, model)

        if not resp.success:
            return None, None, pending_actions

        tool_calls = getattr(resp, "tool_calls", None)
        if not tool_calls:
            _log_request(guild_id, prov_name, model, True, resp.latency)
            tool_icons = {
                "web_search": "🔍", "get_time": "🕐", "get_weather": "🌤️",
                "calculate": "🔢", "translate": "🌐", "play_music": "🎵",
                "fetch_url": "📄", "generate_image": "🖼️"
            }
            unique_tools = list(dict.fromkeys(tools_used))
            icons = "".join(tool_icons.get(t, "🔧") for t in unique_tools)
            note = f"{icons} Auto-tools via {prov_name}/{model}" if tools_used else None
            return resp, note, pending_actions

    _log_request(guild_id, prov_name, model, True, resp.latency)
    return resp, f"🔧 Auto-tools ({max_rounds} rounds) via {prov_name}/{model}", pending_actions


# ============================================================
# FALLBACK
# ============================================================

async def execute_with_fallback(messages, mode, preferred_provider, preferred_model, guild_id=0):
    chain = [(preferred_provider, preferred_model)]
    for item in FALLBACK_CHAINS.get(mode, FALLBACK_CHAINS["normal"]):
        if item[0] not in ["duckduckgo", "tavily", "brave", "serper", "jina"] and item not in chain:
            chain.append(item)
    fallback_note, orig_p, orig_m, is_fb = None, preferred_provider, preferred_model, False
    for pname, mid in chain:
        prov = ProviderFactory.get(pname, API_KEYS)
        if not prov or not await prov.health_check(): continue
        log.info(f"Trying {pname}/{mid}")
        resp = await prov.chat(messages, mid)
        if resp.success:
            _log_request(guild_id, pname, mid, True, resp.latency, is_fb)
            if is_fb: fallback_note = f"⚡ {orig_p}/{orig_m} → {pname}/{mid}"
            return resp, fallback_note
        log.warning(f"Failed: {pname}/{mid}")
        _log_request(guild_id, pname, mid, False, resp.latency, is_fb, resp.error)
        is_fb = True
    return AIResponse(False, "Semua provider tidak tersedia.", "none", "none", error="exhausted"), None

# ============================================================
# SYSTEM PROMPTS
# ============================================================

SYSTEM_PROMPTS = {
    "normal": """You are a helpful AI assistant in a Discord server.
You can see who is talking by their name in [brackets].
Multiple users may be chatting — address them by name when appropriate.
Remember full conversation context. Respond in user's language. Be concise and friendly.

When you receive tool results (such as web search, weather, time, or translation results), 
use that information naturally in your answer.
Do NOT list sources, URLs, or citations. Do NOT use numbered references like [1][2][3].
Just answer naturally as if you already knew the information.
Never say "I cannot access real-time data" when tool results are provided.

IMPORTANT — URL HANDLING:
When a user shares ANY URL/link (https://...), you MUST use the fetch_url tool to read it.
NEVER say "I cannot access the link" — always try fetch_url first.
This works for: news articles, tweets, YouTube, TikTok, Instagram, GitHub, blogs, any website.

For music: you can play, skip, pause, resume, and stop music.
If user is NOT in a voice channel, tell them to join one first.

For images: you can generate images from text descriptions.""",

    "reasoning": """You are a reasoning AI. Think step by step.
Multiple users may ask questions — keep track of who asked what.
Do not use <think> tags. Explain naturally. Respond in user's language.""",

    "search": """You are a helpful AI assistant with access to current information.
Answer the user's question naturally using the search results provided.
Do NOT list sources, URLs, or citations. Do NOT use numbered references.
Just incorporate the information naturally into your response.
Respond in user's language. Be conversational and helpful.""",

    "with_skill": """You are a helpful AI assistant.
Present tool results naturally as part of your response.
Do NOT list sources or references. Just answer naturally.
Respond in the same language as the user.""",
}

# ============================================================
# MAIN HANDLER
# ============================================================

async def handle_message(content: str, settings: Dict, channel_id: int = 0, user_id: int = 0, user_name: str = "User") -> Dict:
    mode = settings.get("active_mode", "normal")
    guild_id = settings.get("guild_id", 0)
    
    history = get_conversation(guild_id, channel_id, limit=30)
    
    # =========================================================
    # STEP 1: Try smart skills (time, weather, calendar)
    # =========================================================
    
    skill_result = None
    try:
        from skills.detector import SkillDetector
        skill_result = await SkillDetector.detect_and_execute(content)
    except Exception as e:
        log.warning(f"Skill detection error: {e}")
    
    if skill_result:
        profile = settings.get("profiles", {}).get(mode, {"provider": "groq", "model": "llama-3.3-70b-versatile"})
        prov, mid = profile.get("provider", "groq"), profile.get("model", "llama-3.3-70b-versatile")
        
        msgs = [
            {"role": "system", "content": SYSTEM_PROMPTS["with_skill"]},
            *[{"role": m["role"], "content": m["content"]} for m in history],
            {"role": "user", "content": f"[{user_name}] bertanya: {content}\n\nHasil tool:\n{skill_result}\n\nSampaikan informasi ini secara natural."}
        ]
        
        resp, fb_note = await execute_with_fallback(msgs, mode, prov, mid, guild_id)
        text = strip_think_tags(resp.content) if resp.success else skill_result
        
        save_message(guild_id, channel_id, user_id, user_name, "user", content)
        save_message(guild_id, channel_id, user_id, user_name, "assistant", text)
        
        return {"text": text, "fallback_note": fb_note if resp.success else None, "actions": []}
    
    # =========================================================
    # STEP 2: Auto-detect mode
    # =========================================================
    
    if settings.get("auto_detect"):
        detected = ModeDetector.detect(content)
        if detected != "normal":
            mode = detected
    
        # =========================================================
    # STEP 2B: Auto Tool Calling
    # =========================================================
    
    profile = settings.get("profiles", {}).get(mode, {"provider": "groq", "model": "llama-3.3-70b-versatile"})
    prov, mid = profile.get("provider", "groq"), profile.get("model", "llama-3.3-70b-versatile")
    
    from core.providers import supports_tool_calling
    if supports_tool_calling(prov):
        system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["normal"])
        formatted_history = []
        for msg in history:
            if msg["role"] == "user" and msg.get("user_name"):
                formatted_history.append({"role": "user", "content": f"[{msg['user_name']}]: {msg['content']}"})
            else:
                formatted_history.append({"role": msg["role"], "content": msg["content"]})
        
        voice_ctx = ""
        if settings.get("user_in_voice"):
            voice_ctx = f" [in voice channel: {settings.get('user_voice_channel', 'yes')}]"
        else:
            voice_ctx = " [not in voice channel]"
        
        # ── URL Detection: inject hint so AI uses fetch_url ──
        user_content = f"[{user_name}]{voice_ctx}: {content}"
        urls = re.findall(r'https?://[^\s<>"\']+', content)
        if urls:
            url_hint = f"\n\n[System hint: User shared {len(urls)} URL(s). Use fetch_url tool to read the content. URLs: {', '.join(urls)}]"
            user_content += url_hint
        
        tool_msgs = [
            {"role": "system", "content": system_prompt},
            *formatted_history,
            {"role": "user", "content": user_content}
        ]
        
        tool_resp, tool_note, tool_actions = await handle_with_tools(tool_msgs, prov, mid, guild_id)
        if tool_resp and tool_resp.success:
            text = strip_think_tags(tool_resp.content) or "Tidak ada jawaban."
            save_message(guild_id, channel_id, user_id, user_name, "user", content)
            save_message(guild_id, channel_id, user_id, user_name, "assistant", text)
            return {"text": text, "fallback_note": tool_note, "actions": tool_actions}
    
    # =========================================================
    # STEP 3: Regular AI chat (Fallback)
    # =========================================================
    
    profile = settings.get("profiles", {}).get(mode, {"provider": "groq", "model": "llama-3.3-70b-versatile"})
    prov, mid = profile.get("provider", "groq"), profile.get("model", "llama-3.3-70b-versatile")
    system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["normal"])
    
    formatted_history = []
    for msg in history:
        if msg["role"] == "user" and msg.get("user_name"):
            formatted_history.append({"role": "user", "content": f"[{msg['user_name']}]: {msg['content']}"})
        else:
            formatted_history.append({"role": msg["role"], "content": msg["content"]})
    
    if mode == "search" and not is_grounding_model(prov, mid):
        search_res = await do_search(content, profile.get("engine", "duckduckgo"))
        msgs = [
            {"role": "system", "content": system_prompt},
            *formatted_history,
            {"role": "user", "content": f"[{user_name}]: {content}\n\nHasil pencarian:\n{search_res}"}
        ]
    else:
        msgs = [
            {"role": "system", "content": system_prompt},
            *formatted_history,
            {"role": "user", "content": f"[{user_name}]: {content}"}
        ]
    
    resp, fb_note = await execute_with_fallback(msgs, mode, prov, mid, guild_id)
    
    if resp.success:
        text = strip_think_tags(resp.content) or "Tidak ada jawaban."
        save_message(guild_id, channel_id, user_id, user_name, "user", content)
        save_message(guild_id, channel_id, user_id, user_name, "assistant", text)
        return {"text": text, "fallback_note": fb_note, "actions": []}
    return {"text": resp.content, "fallback_note": None, "actions": []}
