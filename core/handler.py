"""
Message Handler + Conversation Memory + Smart Skills
Bot otomatis detect kapan harus pakai skill/search/chat biasa
"""
import logging
import re
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from core.providers import ProviderFactory, AIResponse
from config import API_KEYS, FALLBACK_CHAINS, PROVIDERS

log = logging.getLogger(__name__)

# ============================================================
# CONVERSATION MEMORY
# ============================================================

conversation_memory = defaultdict(lambda: defaultdict(lambda: {"messages": [], "last_activity": None}))
MAX_MEMORY_MESSAGES = 20
MEMORY_EXPIRE_MINUTES = 30

def get_conversation(guild_id: int, channel_id: int) -> list:
    conv = conversation_memory[guild_id][channel_id]
    if conv["last_activity"] and datetime.now() - conv["last_activity"] > timedelta(minutes=MEMORY_EXPIRE_MINUTES):
        conv["messages"], conv["last_activity"] = [], None
    return conv["messages"].copy()

def add_to_conversation(guild_id: int, channel_id: int, role: str, content: str):
    conv = conversation_memory[guild_id][channel_id]
    conv["messages"].append({"role": role, "content": content})
    conv["last_activity"] = datetime.now()
    if len(conv["messages"]) > MAX_MEMORY_MESSAGES:
        conv["messages"] = conv["messages"][-MAX_MEMORY_MESSAGES:]

def clear_conversation(guild_id: int, channel_id: int = None):
    if channel_id:
        conversation_memory[guild_id][channel_id] = {"messages": [], "last_activity": None}
    else:
        conversation_memory[guild_id] = defaultdict(lambda: {"messages": [], "last_activity": None})

def get_memory_stats(guild_id: int) -> dict:
    if guild_id not in conversation_memory:
        return {"channels": 0, "total_messages": 0}
    return {"channels": len(conversation_memory[guild_id]), "total_messages": sum(len(c["messages"]) for c in conversation_memory[guild_id].values())}

# ============================================================
# REQUEST LOGS
# ============================================================

request_logs: List[Dict] = []
MAX_LOGS = 500

def _log_request(guild_id, provider, model, success, latency, is_fallback=False, error=None):
    request_logs.append({"guild_id": guild_id, "provider": provider, "model": model, "success": success, "latency": latency, "is_fallback": is_fallback, "error": error, "time": datetime.now().strftime("%H:%M:%S")})
    if len(request_logs) > MAX_LOGS:
        request_logs.pop(0)

PROVIDER_ICONS = {"groq": "🐆", "openrouter": "🧭", "pollinations": "🐝", "gemini": "🔷", "cloudflare": "☁️", "huggingface": "🤗", "cerebras": "🧠", "cohere": "🧵", "siliconflow": "🧪", "routeway": "🛣️", "mlvoca": "🦙"}

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
def is_grounding_model(p: str, m: str) -> bool: return (p, m) in GROUNDING_MODELS

# ============================================================
# SMART MODE DETECTOR
# ============================================================

class ModeDetector:
    SEARCH_KW = [
        "berita terbaru", "berita hari ini", "harga sekarang", "update terbaru",
        "kabar terbaru", "news today", "current price", "latest news",
        "stock price", "kurs dollar", "hasil pertandingan", "jadwal hari ini",
        "siapa yang menang", "skor pertandingan",
    ]
    REASON_KW = [
        "jelaskan step by step", "langkah demi langkah", "hitung ",
        "analisis ", "buktikan ", "solve ", "calculate ", "analyze ",
        "tulis kode", "write code", "debug ", "buatkan program",
    ]
    
    @classmethod
    def detect(cls, content: str) -> str:
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
    "normal": """You are a helpful AI assistant with access to real-time tools.
You can check time, weather, calendar, and search the internet.
When tool results are provided, use them naturally in your response.
Remember conversation context. Respond in user's language. Be concise.""",

    "reasoning": """You are a reasoning AI. Think step by step.
Do not use <think> tags. Explain naturally. Respond in user's language.""",

    "search": """You are an AI with web search results.
Answer based on search results AND conversation context.
Cite URLs when relevant. Respond in user's language.""",

    "search_grounding": """You are an AI with web search capability.
Use conversation context for follow-up questions.
Find current info. Cite sources. Respond in user's language.""",

    "with_skill": """You are a helpful AI assistant. Tool results are provided below.
Present the information naturally and conversationally.
If the user asked a follow-up question, use conversation context.
Respond in the same language as the user.""",
}

# ============================================================
# MAIN HANDLER - WITH SMART SKILLS
# ============================================================

async def handle_message(content: str, settings: Dict, channel_id: int = 0) -> Dict:
    mode = settings.get("active_mode", "normal")
    guild_id = settings.get("guild_id", 0)
    
    history = get_conversation(guild_id, channel_id)
    
    # =========================================================
    # STEP 1: Try smart skills first (time, weather, calendar)
    # =========================================================
    
    skill_result = None
    try:
        from skills.detector import SkillDetector
        skill_result = await SkillDetector.detect_and_execute(content)
    except Exception as e:
        log.warning(f"Skill detection error: {e}")
    
    if skill_result:
        log.info(f"Skill matched, enriching with AI")
        
        # Use AI to make skill result more natural
        profile = settings.get("profiles", {}).get(mode, {"provider": "groq", "model": "llama-3.3-70b-versatile"})
        prov, mid = profile.get("provider", "groq"), profile.get("model", "llama-3.3-70b-versatile")
        
        msgs = [
            {"role": "system", "content": SYSTEM_PROMPTS["with_skill"]},
            *history,
            {"role": "user", "content": f"User bertanya: {content}\n\nHasil tool:\n{skill_result}\n\nSampaikan informasi ini secara natural dan ramah."}
        ]
        
        resp, fb_note = await execute_with_fallback(msgs, mode, prov, mid, guild_id)
        
        if resp.success:
            text = strip_think_tags(resp.content) or skill_result
        else:
            # Fallback: return raw skill result if AI fails
            text = skill_result
            fb_note = None
        
        add_to_conversation(guild_id, channel_id, "user", content)
        add_to_conversation(guild_id, channel_id, "assistant", text)
        return {"text": text, "fallback_note": fb_note if resp.success else None}
    
    # =========================================================
    # STEP 2: Auto-detect search mode (only on first message)
    # =========================================================
    
    if settings.get("auto_detect") and len(history) == 0:
        detected = ModeDetector.detect(content)
        if detected != "normal":
            mode = detected
            log.info(f"Auto-detected mode: {mode}")
    
    # =========================================================
    # STEP 3: Regular AI chat with memory
    # =========================================================
    
    profile = settings.get("profiles", {}).get(mode, {"provider": "groq", "model": "llama-3.3-70b-versatile"})
    prov, mid = profile.get("provider", "groq"), profile.get("model", "llama-3.3-70b-versatile")
    system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["normal"])
    
    if mode == "search" and not is_grounding_model(prov, mid):
        search_res = await do_search(content, profile.get("engine", "duckduckgo"))
        context = ""
        if history:
            context = "Percakapan sebelumnya:\n"
            for msg in history[-6:]:
                role = "User" if msg["role"] == "user" else "Bot"
                context += f"{role}: {msg['content'][:200]}\n"
            context += "\n"
        msgs = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{context}Pertanyaan: {content}\n\nHasil pencarian:\n{search_res}"}
        ]
    else:
        msgs = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": content}
        ]
    
    resp, fb_note = await execute_with_fallback(msgs, mode, prov, mid, guild_id)
    
    if resp.success:
        text = strip_think_tags(resp.content) or "Tidak ada jawaban."
        add_to_conversation(guild_id, channel_id, "user", content)
        add_to_conversation(guild_id, channel_id, "assistant", text)
        return {"text": text, "fallback_note": fb_note}
    return {"text": resp.content, "fallback_note": None}
