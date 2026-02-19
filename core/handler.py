"""
Message Handler + Fallback Manager
Plaintext responses + fallback notice + think stripping + search
"""

import logging
import re
import time
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from core.providers import ProviderFactory, AIResponse
from config import API_KEYS, FALLBACK_CHAINS, PROVIDERS

log = logging.getLogger(__name__)

# ============================================================
# IN-MEMORY REQUEST LOGS
# ============================================================

request_logs: List[Dict] = []
MAX_LOGS = 500

def _log_request(guild_id, provider, model, success, latency, is_fallback=False, error=None):
    request_logs.append({
        "guild_id": guild_id,
        "provider": provider,
        "model": model,
        "success": success,
        "latency": latency,
        "is_fallback": is_fallback,
        "error": error,
        "time": datetime.now().strftime("%H:%M:%S"),
    })
    if len(request_logs) > MAX_LOGS:
        request_logs.pop(0)

# ============================================================
# PROVIDER ICONS
# ============================================================

PROVIDER_ICONS = {
    "groq":        "🐆",
    "openrouter":  "🧭",
    "pollinations":"🐝",
    "gemini":      "🔷",
    "cloudflare":  "☁️",
    "huggingface": "🤗",
    "cerebras":    "🧠",
    "cohere":      "🧵",
    "siliconflow": "🧪",
    "routeway":    "🛣️",
    "mlvoca":      "🦙",
}

# ============================================================
# THINK TAG STRIPPER
# ============================================================

def strip_think_tags(content: str) -> str:
    """
    Remove <think>...</think> blocks from reasoning model output.
    Also handles variations: <thinking>, <thought>, etc.
    """
    # Remove <think>...</think> (greedy, multiline)
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
    content = re.sub(r'<thinking>.*?</thinking>', '', content, flags=re.DOTALL)
    content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL)
    
    # Remove standalone opening/closing tags (jika tidak berpasangan)
    content = re.sub(r'</?think>', '', content)
    content = re.sub(r'</?thinking>', '', content)
    content = re.sub(r'</?thought>', '', content)
    
    # Clean up excessive newlines left behind
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    return content.strip()

# ============================================================
# MODE DETECTOR
# ============================================================

class ModeDetector:
    """Auto-detect mode from message content"""
    
    SEARCH_KEYWORDS = [
        # Bahasa Indonesia
        "berita", "terbaru", "hari ini", "sekarang",
        "harga", "cuaca", "saat ini", "update terbaru",
        "kabar terbaru", "info terkini", "siapa presiden",
        # English
        "news", "today", "current", "latest", "price",
        "weather", "who is", "what happened", "right now",
        "how much", "stock price",
        # Temporal
        "2025", "2026", "kemarin", "yesterday",
    ]

    REASONING_KEYWORDS = [
        # Bahasa Indonesia
        "jelaskan step", "langkah demi langkah", "buktikan",
        "analisis", "hitung", "selesaikan", "bandingkan",
        "evaluasi", "logika", "matematika", "kode program",
        "mengapa bisa", "bagaimana caranya",
        # English
        "step by step", "prove", "analyze", "calculate",
        "solve", "compare", "evaluate", "logic",
        "math", "code", "program", "explain how",
        "why does", "reason",
    ]

    @classmethod
    def detect(cls, content: str) -> str:
        lower = content.lower()
        for kw in cls.SEARCH_KEYWORDS:
            if kw in lower:
                return "search"
        for kw in cls.REASONING_KEYWORDS:
            if kw in lower:
                return "reasoning"
        return "normal"

# ============================================================
# SEARCH HANDLER
# ============================================================

async def do_search(query: str, engine: str = "duckduckgo") -> str:
    """Perform web search, return formatted results"""
    try:
        if engine == "duckduckgo":
            from duckduckgo_search import DDGS

            def _search():
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=5))

            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, _search)

            if not results:
                return "Tidak ada hasil pencarian."

            lines = []
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. {r['title']}\n   {r['body'][:150]}\n   {r['href']}")
            return "\n\n".join(lines)

        return "Search engine tidak tersedia."

    except Exception as e:
        log.error(f"Search error: {e}")
        return f"Search gagal: {e}"

# ============================================================
# GROUNDING-CAPABLE MODELS
# ============================================================

# Models that have BUILT-IN web search (no need for manual search)
GROUNDING_MODELS = {
    # Pollinations models with built-in search
    ("pollinations", "gemini-search"),
    ("pollinations", "perplexity-fast"),
    ("pollinations", "perplexity-reasoning"),
}

def is_grounding_model(provider: str, model: str) -> bool:
    """Check if this provider+model has built-in web search"""
    return (provider, model) in GROUNDING_MODELS

# ============================================================
# FALLBACK EXECUTOR
# ============================================================

async def execute_with_fallback(
    messages: List[Dict],
    mode: str,
    preferred_provider: str,
    preferred_model: str,
    guild_id: int = 0,
) -> Tuple[AIResponse, Optional[str]]:
    """
    Execute with fallback chain.
    Returns (response, fallback_note_or_None)
    """

    chain = [(preferred_provider, preferred_model)]

    fallback = FALLBACK_CHAINS.get(mode, FALLBACK_CHAINS["normal"])
    for item in fallback:
        pname, _ = item
        if pname in ["duckduckgo", "tavily", "brave", "serper", "jina"]:
            continue
        if item not in chain:
            chain.append(item)

    fallback_note = None
    original_provider = preferred_provider
    original_model = preferred_model
    is_fallback = False

    for provider_name, model_id in chain:
        provider = ProviderFactory.get(provider_name, API_KEYS)
        if not provider:
            continue

        if not await provider.health_check():
            continue

        log.info(f"Trying {provider_name}/{model_id}")
        response = await provider.chat(messages, model_id)

        if response.success:
            _log_request(guild_id, provider_name, model_id, True, response.latency, is_fallback)

            if is_fallback:
                icon_orig = PROVIDER_ICONS.get(original_provider, "📦")
                icon_new = PROVIDER_ICONS.get(provider_name, "📦")
                fallback_note = (
                    f"⚡ {icon_orig} {original_provider}/{original_model} tidak tersedia "
                    f"→ pakai {icon_new} {provider_name}/{model_id}"
                )

            return response, fallback_note
        else:
            log.warning(f"Failed: {provider_name}/{model_id} — {response.error}")
            _log_request(guild_id, provider_name, model_id, False, response.latency, is_fallback, response.error)
            is_fallback = True

    fail_response = AIResponse(
        success=False,
        content="Maaf, semua provider sedang tidak tersedia. Coba lagi nanti.",
        provider="none",
        model="none",
        error="All providers exhausted"
    )
    return fail_response, None

# ============================================================
# SYSTEM PROMPTS
# ============================================================

SYSTEM_PROMPTS = {
    "normal": (
        "You are a helpful, friendly AI assistant. "
        "Be conversational, concise, and natural. "
        "Respond in the same language as the user."
    ),
    "reasoning": (
        "You are an advanced reasoning AI. "
        "Think through problems carefully and provide clear answers. "
        "Show your work and reasoning steps. "
        "Do NOT wrap your thinking in <think> tags. "
        "Just explain your reasoning naturally. "
        "Respond in the same language as the user."
    ),
    "search": (
        "You are a helpful AI with web search results. "
        "Answer based on the search results provided. "
        "Cite sources with URLs when possible. Be factual. "
        "Respond in the same language as the user."
    ),
    "search_grounding": (
        "You are a helpful AI assistant with web search capability. "
        "Search the web to find current and accurate information. "
        "Cite sources when possible. Be factual and up-to-date. "
        "Respond in the same language as the user."
    ),
}

# ============================================================
# MAIN HANDLER
# ============================================================

async def handle_message(content: str, settings: Dict) -> Dict:
    """
    Handle user message.
    Returns: {"text": str, "fallback_note": str|None}
    """

    active_mode = settings.get("active_mode", "normal")
    auto_detect = settings.get("auto_detect", False)
    profiles = settings.get("profiles", {})
    guild_id = settings.get("guild_id", 0)

    # Auto-detect mode if enabled
    mode = active_mode
    if auto_detect:
        detected = ModeDetector.detect(content)
        if detected != "normal":
            mode = detected
            log.info(f"Auto-detected mode: {mode}")

    # Get profile for this mode
    profile = profiles.get(mode, profiles.get("normal", {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile"
    }))

    provider_name = profile.get("provider", "groq")
    model_id = profile.get("model", "llama-3.3-70b-versatile")

    # =========================================================
    # SEARCH MODE — 2 approaches
    # =========================================================

    if mode == "search":
        # Approach 1: Model has BUILT-IN grounding (all-in-one)
        if is_grounding_model(provider_name, model_id):
            log.info(f"Using grounding model: {provider_name}/{model_id}")
            messages = [
                {"role": "system", "content": SYSTEM_PROMPTS["search_grounding"]},
                {"role": "user", "content": content}
            ]
        
        # Approach 2: Manual search → feed results to LLM
        else:
            log.info(f"Manual search + LLM summarization")
            engine = profile.get("engine", "duckduckgo")
            search_results = await do_search(content, engine)
            
            messages = [
                {"role": "system", "content": SYSTEM_PROMPTS["search"]},
                {
                    "role": "user",
                    "content": (
                        f"Pertanyaan: {content}\n\n"
                        f"Hasil Pencarian:\n{search_results}\n\n"
                        f"Jawab berdasarkan hasil pencarian di atas. "
                        f"Sertakan link sumber."
                    )
                }
            ]
    
    # =========================================================
    # NORMAL / REASONING MODE
    # =========================================================
    else:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["normal"])},
            {"role": "user", "content": content}
        ]

    # Execute with fallback
    response, fallback_note = await execute_with_fallback(
        messages=messages,
        mode=mode,
        preferred_provider=provider_name,
        preferred_model=model_id,
        guild_id=guild_id,
    )

    if response.success:
        # ===== STRIP THINK TAGS =====
        clean_text = strip_think_tags(response.content)
        
        # Jika setelah strip kosong (hanya ada think block), minta ulang
        if not clean_text:
            clean_text = "Hmm, saya sudah memikirkannya tapi tidak menghasilkan jawaban. Coba tanyakan lagi dengan cara berbeda."
        
        return {
            "text": clean_text,
            "fallback_note": fallback_note
        }
    else:
        return {
            "text": response.content,
            "fallback_note": None
        }
