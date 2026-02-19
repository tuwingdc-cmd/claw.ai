"""
Message Handler + DB-backed Conversation Memory + Smart Skills
"""
import logging
import re
import asyncio
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
# SEARCH
# ============================================================

async def do_search(query: str, engine: str = "duckduckgo") -> str:
    try:
        if engine == "duckduckgo":
            from duckduckgo_search import DDGS
            def _s():
                with DDGS() as d: return list(d.text(query, max_results=5))
            results = await asyncio.get_event_loop().run_in_executor(None, _s)
            if not results: return "Tidak ada hasil."
            return "\n\n".join([f"{i}. {r['title']}\n   {r['body'][:150]}\n   {r['href']}" for i, r in enumerate(results, 1)])
    except Exception as e:
        return f"Search error: {e}"
    return "Search tidak tersedia."

GROUNDING_MODELS = {("groq", "groq/compound"), ("groq", "groq/compound-mini"), ("groq", "compound-beta"), ("groq", "compound-beta-mini"), ("pollinations", "gemini-search"), ("pollinations", "perplexity-fast"), ("pollinations", "perplexity-reasoning")}
def is_grounding_model(p, m): return (p, m) in GROUNDING_MODELS

# ============================================================
# TOOL DEFINITIONS (untuk Auto Tool Calling)
# ============================================================
WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the internet for real-time information. "
            "Use this when asked about: current events, news, prices, "
            "who is president/leader/CEO, sports results, weather, "
            "anything that might have changed recently, or any fact "
            "you are not confident about."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query in the most relevant language"
                }
            },
            "required": ["query"]
        }
    }
}

TOOLS_LIST = [WEB_SEARCH_TOOL]



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
# FALLBACK
# ============================================================


# ============================================================
# TOOL CALL EXECUTOR
# ============================================================
async def execute_tool_call(tool_name: str, tool_args: dict) -> str:
    """Eksekusi tool yang diminta AI"""
    if tool_name == "web_search":
        query = tool_args.get("query", "")
        log.info(f"🔍 AI requested search: {query}")
        return await do_search(query)
    return f"Unknown tool: {tool_name}"

async def handle_with_tools(messages: list, prov_name: str, model: str, 
                             guild_id: int = 0) -> tuple:
    """
    Kirim ke AI dengan tools, handle tool_calls response,
    jalankan tool, kirim balik ke AI, dapat jawaban final.
    """
    from core.providers import supports_tool_calling
    
    # Cek apakah provider support tools
    if not supports_tool_calling(prov_name):
        return None, None  # Signal: pakai fallback biasa
    
    prov = ProviderFactory.get(prov_name, API_KEYS)
    if not prov or not await prov.health_check():
        return None, None
    
    # Round 1: Kirim ke AI dengan tools
    log.info(f"🤖 Tool calling: {prov_name}/{model}")
    resp = await prov.chat(messages, model, tools=TOOLS_LIST, tool_choice="auto")
    
    if not resp.success:
        return None, None
    
    import json
    content_raw = resp.content
    
    # Cek apakah AI minta tool call
    # Tool calls biasanya ada di response sebagai JSON khusus
    # Groq/OpenRouter return tool_calls dalam content atau structured
    tool_call_data = None
    tool_calls = getattr(resp, "tool_calls", None)
    if not tool_calls:
        # AI tidak perlu tool → langsung return jawaban
        return resp, None

    tool_call_data = tool_calls[0]
    
    # AI minta search! Eksekusi tool
    fn_name = tool_call_data.get("function", {}).get("name", "")
    fn_args_str = tool_call_data.get("function", {}).get("arguments", "{}")
    tool_call_id = tool_call_data.get("id", "call_0")
    
    try:
        fn_args = json.loads(fn_args_str)
    except:
        fn_args = {"query": content_raw}
    
    tool_result = await execute_tool_call(fn_name, fn_args)
    log.info(f"✅ Tool executed: {fn_name}")
    
    # Round 2: Kirim hasil tool ke AI, minta jawaban final
    messages_with_tool = messages + [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [tool_call_data]
        },
        {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": tool_result
        }
    ]
    
    final_resp = await prov.chat(messages_with_tool, model)
    if final_resp.success:
        _log_request(guild_id, prov_name, model, True, final_resp.latency)
        return final_resp, f"🔍 Auto-searched via {prov_name}/{model}"
    
    return None, None

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
Remember full conversation context. Respond in user's language. Be concise and friendly.""",

    "reasoning": """You are a reasoning AI. Think step by step.
Multiple users may ask questions — keep track of who asked what.
Do not use <think> tags. Explain naturally. Respond in user's language.""",

    "search": """You are an AI with web search results.
Answer based on search results AND conversation context.
Cite URLs when relevant. Respond in user's language.""",

    "with_skill": """You are a helpful AI assistant. Tool results are provided below.
Present the information naturally. Track who asked what.
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
        
        # Save to database
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
        # Build messages untuk tool calling
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
        # Kalau tool calling gagal, lanjut ke STEP 3 biasa
    
    # =========================================================
    # STEP 3: Regular AI chat with DB memory (Fallback)
    # =========================================================
    
    profile = settings.get("profiles", {}).get(mode, {"provider": "groq", "model": "llama-3.3-70b-versatile"})
    prov, mid = profile.get("provider", "groq"), profile.get("model", "llama-3.3-70b-versatile")
    system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["normal"])
    
    # Build messages with user identification
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
        
        # Save to database
        save_message(guild_id, channel_id, user_id, user_name, "user", content)
        save_message(guild_id, channel_id, user_id, user_name, "assistant", text)
        
        return {"text": text, "fallback_note": fb_note}
    return {"text": resp.content, "fallback_note": None}
