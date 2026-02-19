"""
Message Handler + Fallback Manager
Plaintext responses + fallback notice
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from core.providers import ProviderFactory, AIResponse
from config import API_KEYS, FALLBACK_CHAINS, PROVIDERS

log = logging.getLogger(__name__)

# ============================================================
# IN-MEMORY REQUEST LOGS (replaced by DB later)
# ============================================================

request_logs: List[Dict] = []

MAX_LOGS = 500

def _log_request(guild_id: int, provider: str, model: str, success: bool, latency: float, is_fallback: bool = False, error: str = None):
    """Store request log"""
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
    # Keep log size in check
    if len(request_logs) > MAX_LOGS:
        request_logs.pop(0)

# ============================================================
# PROVIDER ICONS (import from main)
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
# MODE DETECTOR
# ============================================================

class ModeDetector:
    SEARCH_KEYWORDS = [
        "berita", "news", "terbaru", "hari ini", "today",
        "harga", "price", "cuaca", "weather", "sekarang",
        "current", "update", "latest", "2025", "2026",
        "siapa presiden", "who is", "what happened",
    ]

    REASONING_KEYWORDS = [
        "jelaskan step", "step by step", "langkah",
        "buktikan", "prove", "analisis", "analyze",
        "hitung", "calculate", "solve", "selesaikan",
        "bandingkan", "compare", "evaluasi", "evaluate",
        "matematika", "math", "code", "kode", "program",
        "logika", "logic", "reason",
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
            import asyncio

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
    Execute request with fallback.
    Returns (response, fallback_note_or_None)
    """

    # Build chain: preferred first, then fallback
    chain = [(preferred_provider, preferred_model)]

    fallback = FALLBACK_CHAINS.get(mode, FALLBACK_CHAINS["normal"])
    for item in fallback:
        pname, _ = item
        # Skip search-only entries
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
            # Log it
            _log_request(guild_id, provider_name, model_id, True, response.latency, is_fallback)

            # If this wasn't the preferred, build fallback note
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
            is_fallback = True  # Next attempt is a fallback

    # All failed
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
        "Think step by step. Show your reasoning process. "
        "Be thorough and precise. "
        "Respond in the same language as the user."
    ),
    "search": (
        "You are a helpful AI with web search results. "
        "Answer based on the search results provided. "
        "Cite sources when possible. Be factual. "
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

    # Get profile for this mode
    profile = profiles.get(mode, profiles.get("normal", {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile"
    }))

    provider = profile.get("provider", "groq")
    model = profile.get("model", "llama-3.3-70b-versatile")

    # Build messages
    system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["normal"])
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content}
    ]

    # If search mode: get search results first, inject into prompt
    if mode == "search":
        engine = profile.get("engine", "duckduckgo")
        search_results = await do_search(content, engine)

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Pertanyaan: {content}\n\n"
                    f"Hasil Pencarian:\n{search_results}\n\n"
                    f"Jawab berdasarkan hasil pencarian di atas."
                )
            }
        ]

    # Execute with fallback
    response, fallback_note = await execute_with_fallback(
        messages=messages,
        mode=mode,
        preferred_provider=provider,
        preferred_model=model,
        guild_id=guild_id,
    )

    if response.success:
        return {
            "text": response.content,
            "fallback_note": fallback_note
        }
    else:
        return {
            "text": response.content,  # "Maaf, semua provider..."
            "fallback_note": None
        }
