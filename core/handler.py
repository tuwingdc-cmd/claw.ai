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

GROUNDING_MODELS = {("pollinations", "gemini-search"), ("pollinations", "perplexity-fast"), ("pollinations", "perplexity-reasoning")}
def is_grounding_model(p, m): return (p, m) in GROUNDING_MODELS

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
    
    if settings.get("auto_detect") and len(history) == 0:
        detected = ModeDetector.detect(content)
        if detected != "normal":
            mode = detected
    
    # =========================================================
    # STEP 3: Regular AI chat with DB memory
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
