"""
Message Handler + DB-backed Conversation Memory + Smart Skills + Tools
"""
import json
import math
import logging
import re
import asyncio
import aiohttp
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
MEMORY_EXPIRE_MINUTES = 0  # No expiry, DB-based now

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
    """Search with Tavily first (more accurate), fallback to DuckDuckGo"""

    # ── TAVILY (lebih akurat untuk data terkini) ──
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

    # ── DUCKDUCKGO (fallback, gratis unlimited) ──
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
    """
    Translate using AI for natural, native-sounding results.
    Understands slang, idioms, and context.
    """
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

    # Pakai model cepat dan ringan untuk translate
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
# TOOL DEFINITIONS (5 Tools)
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
                "text": {
                    "type": "string",
                    "description": "The text to translate"
                },
                "target_language": {
                    "type": "string",
                    "description": "Target language, e.g. English, Indonesian, Japanese, Korean, Spanish"
                },
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

TOOLS_LIST = [WEB_SEARCH_TOOL, GET_TIME_TOOL, GET_WEATHER_TOOL, CALCULATE_TOOL, TRANSLATE_TOOL]


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
# TOOL CALL EXECUTOR — 5 Tools
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
            # Preprocess common patterns
            expr = expression.replace("^", "**").replace("×", "*").replace("÷", "/")
            # Handle "X% of Y"
            pct_match = re.match(r'([\d.]+)%\s*of\s*([\d.]+)', expr, re.IGNORECASE)
            if pct_match:
                pct, val = float(pct_match.group(1)), float(pct_match.group(2))
                result = pct / 100 * val
                return f"{expression} = {result}"
            # Safe eval
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

    return f"Unknown tool: {tool_name}"


# ============================================================
# TOOL CALLING HANDLER
# ============================================================

async def handle_with_tools(messages: list, prov_name: str, model: str,
                             guild_id: int = 0) -> tuple:
    """
    Kirim ke AI dengan tools, handle tool_calls response,
    jalankan SEMUA tools, kirim balik ke AI.
    Support multi-round (AI bisa panggil tool berkali-kali).
    """
    from core.providers import supports_tool_calling

    if not supports_tool_calling(prov_name):
        return None, None

    prov = ProviderFactory.get(prov_name, API_KEYS)
    if not prov or not await prov.health_check():
        return None, None

    log.info(f"🤖 Tool calling: {prov_name}/{model}")
    resp = await prov.chat(messages, model, tools=TOOLS_LIST, tool_choice="auto")

    if not resp.success:
        return None, None

    tool_calls = getattr(resp, "tool_calls", None)
    if not tool_calls:
        return resp, None

    # ── Multi-round tool calling loop ──
    max_rounds = 3
    current_messages = list(messages)
    tools_used = []

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

            tool_result = await execute_tool_call(fn_name, fn_args)
            log.info(f"✅ Round {round_num + 1}: {fn_name}")
            tools_used.append(fn_name)

            current_messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": tool_result
            })

        # Kirim balik ke AI tanpa tools agar langsung jawab
        resp = await prov.chat(current_messages, model)

        if not resp.success:
            return None, None

        tool_calls = getattr(resp, "tool_calls", None)
        if not tool_calls:
            _log_request(guild_id, prov_name, model, True, resp.latency)
            # Build note dengan emoji sesuai tool yang dipakai
            tool_icons = {
                "web_search": "🔍", "get_time": "🕐", "get_weather": "🌤️",
                "calculate": "🔢", "translate": "🌐"
            }
            unique_tools = list(dict.fromkeys(tools_used))  # maintain order, remove dupes
            icons = "".join(tool_icons.get(t, "🔧") for t in unique_tools)
            note = f"{icons} Auto-tools via {prov_name}/{model}" if tools_used else None
            return resp, note

    _log_request(guild_id, prov_name, model, True, resp.latency)
    return resp, f"🔧 Auto-tools ({max_rounds} rounds) via {prov_name}/{model}"


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
Remember full conversation context. Respond in user's language. Be concise and frequired

When you receive tool results (such as web search, weather, time, or translation results), 
use that information naturally in your answer.TOOLNOT list sources, URLs, or citations. Do NOT use numbered references like [1][2][3].
Just answer naturally as if you already knew the information.
Never say "I cannot access real-time data" when tool results are provided.""",

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
    
    # Get conversation history from DATABASE
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
        
        return {"text": text, "fallback_note": fb_note if resp.success else None}
    
    # =========================================================
    # STEP 2: Auto-detect mode
    # =========================================================
    
    if settings.get("auto_detect"):
        detected = ModeDetector.detect(content)
        if detected != "normal":
            mode = detected
    
    # =========================================================
    # STEP 2B: Coba Auto Tool Calling (AI putuskan sendiri)
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
        
        tool_msgs = [
            {"role": "system", "content": system_prompt},
            *formatted_history,
            {"role": "user", "content": f"[{user_name}]: {content}"}
        ]
        
        tool_resp, tool_note = await handle_with_tools(tool_msgs, prov, mid, guild_id)
        if tool_resp and tool_resp.success:
            text = strip_think_tags(tool_resp.content) or "Tidak ada jawaban."
            save_message(guild_id, channel_id, user_id, user_name, "user", content)
            save_message(guild_id, channel_id, user_id, user_name, "assistant", text)
            return {"text": text, "fallback_note": tool_note}
    
    # =========================================================
    # STEP 3: Regular AI chat with DB memory (Fallback)
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
        return {"text": text, "fallback_note": fb_note}
    return {"text": resp.content, "fallback_note": None}
