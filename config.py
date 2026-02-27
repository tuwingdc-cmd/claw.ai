"""
Configuration & Provider Registry
All providers, models, and defaults in one place
— Verified against official docs & manual API testing: Feb 27, 2026 —

CHANGELOG:
- [Cerebras]     HAPUS: llama-3.3-70b & qwen-3-32b (DEPRECATED 16 Feb 2026)
                 HAPUS: gpt-oss-20b (tidak ada di daftar resmi)
- [Groq]         FIX: compound-beta → groq/compound (sesuai test)
                 HAPUS: llama3-groq-*-tool-use, qwen-qwq-32b, deepseek-r1-distill
                        (tidak ada di list model test)
                 TAMBAH: allam-2-7b, kimi-k2-instruct, llama-guard-4-12b
- [OpenRouter]   REVAMP: Tambah semua :free dari test, tambah premium picks
                 TAMBAH: gpt-oss-120b:free, gpt-oss-20b:free,
                         qwen3-coder:free, gemma-3n, liquid, cognitivecomputations,
                         arcee-ai, stepfun, upstage, + premium flagships
- [Gemini]       TAMBAH: gemini-3-pro, gemini-3-flash, gemini-3.1-pro,
                         gemma-3n-e4b-it, gemma-3n-e2b-it dari test
- [Cloudflare]   EXPAND: tambah 15+ model dari test (qwen3-30b, qwq-32b,
                         gpt-oss-120b/20b, granite, flux, whisper, dll)
- [HuggingFace]  EXPAND: tambah model dari test (DeepSeek-V3.2, Qwen3.5,
                         gemma-3-27b, gpt-oss, FLUX, whisper, dll)
- [Cohere]       EXPAND: tambah embed, rerank, aya models dari test
- [SiliconFlow]  EXPAND: tambah 30+ model dari test (GLM-5, ERNIE, Kimi,
                         Qwen3-Coder, VL models, video gen, TTS, dll)
- [SambaNova]    UPDATE: sesuaikan 18 model dari test (tambah V3.1, V3.2,
                         MiniMax-M2.5, ALLaM, Swallow, hapus yang tidak ada)
- [NVIDIA]       EXPAND: tambah 30+ model dari test (Nemotron Ultra 253B,
                         Mistral Large 675B, Qwen3.5-397B, Kimi-K2.5, dll)
- [Mistral]      BARU: provider baru, 15 model dari test
- [OpenAI]       BARU: provider premium, 10 model
- [Anthropic]    BARU: provider premium, 5 model
- [xAI]          BARU: provider premium, 6 model
- [Pollinations] UPDATE: sesuaikan dari test (hapus chickytutor/legacy,
                         tambah qwen-character)
- [Routeway]     OK — tidak ada perubahan
- [Puter]        OK — tidak ada perubahan
- [MLVOCA]       OK — tidak ada perubahan

LEGEND:
🆓 = Free model (no cost)
💎 = Premium / Paid only
⚠️ = Limited free tier (ketat / credit-based)
⭐ = Support Tool Calling (web search, dll)
🔥 = Recommended (fitur lengkap / performa bagus)
👁️ = Vision (bisa lihat gambar)
🧠 = Reasoning mode
🔍 = Search/Grounding built-in
"""

import os
from dotenv import load_dotenv
from typing import Dict, List, Optional
from dataclasses import dataclass, field

load_dotenv()

# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_PREFIX = os.getenv("DISCORD_PREFIX", "!")

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ============================================================
# PROVIDER API KEYS
# ============================================================

API_KEYS = {
    "groq":               os.getenv("GROQ_API_KEY"),
    "openweathermap":     os.getenv("OPENWEATHERMAP_API_KEY"),
    "openrouter":         os.getenv("OPENROUTER_API_KEY"),
    "pollinations":       os.getenv("POLLINATIONS_API_KEY"),
    "gemini":             os.getenv("GEMINI_API_KEY"),
    "cerebras":           os.getenv("CEREBRAS_API_KEY"),
    "sambanova":          os.getenv("SAMBANOVA_API_KEY"),
    "cloudflare":         os.getenv("CLOUDFLARE_API_TOKEN"),
    "cloudflare_account": os.getenv("CLOUDFLARE_ACCOUNT_ID"),
    "huggingface":        os.getenv("HUGGINGFACE_TOKEN"),
    "cohere":             os.getenv("COHERE_API_KEY"),
    "siliconflow":        os.getenv("SILICONFLOW_API_KEY"),
    "routeway":           os.getenv("ROUTEWAY_API_KEY"),
    "nvidia":             os.getenv("NVIDIA_API_KEY"),
    "mistral":            os.getenv("MISTRAL_API_KEY"),
    "openai":             os.getenv("OPENAI_API_KEY"),
    "anthropic":          os.getenv("ANTHROPIC_API_KEY"),
    "xai":                os.getenv("XAI_API_KEY"),
    "tavily":             os.getenv("TAVILY_API_KEY"),
    "brave":              os.getenv("BRAVE_API_KEY"),
    "serper":             os.getenv("SERPER_API_KEY"),
    "puter_api_key":      os.getenv("PUTER_API_KEY"),
}

# ============================================================
# DEFAULTS
# ============================================================

DEFAULTS = {
    "provider":      os.getenv("DEFAULT_PROVIDER", "groq"),
    "model":         os.getenv("DEFAULT_MODEL", "llama-3.3-70b-versatile"),
    "mode":          "normal",
    "auto_chat":     False,
    "auto_detect":   False,
    "search_engine": "duckduckgo",
}

# ============================================================
# PROVIDER REGISTRY
# ============================================================

@dataclass
class Model:
    id: str
    name: str
    modes: List[str] = field(default_factory=lambda: ["normal"])
    context: int = 8192
    vision: bool = False
    tools: bool = False

@dataclass
class Provider:
    name: str
    endpoint: str
    models: List[Model]
    auth_header: str = "Authorization"
    auth_prefix: str = "Bearer"
    free_tier: bool = True
    rate_limit: str = ""

# ============================================================
# PROVIDER DEFINITIONS — UPDATED FEB 27, 2026
# ============================================================

PROVIDERS: Dict[str, Provider] = {

    # ==================== GROQ ====================
    # 🆓 SEMUA MODEL GRATIS — No credit card needed
    # Docs: https://console.groq.com/docs/models
    # Rate: ~14,400 req/hari, ~1M token/hari per model
    # Verified: curl api.groq.com/openai/v1/models — 20 models
    "groq": Provider(
        name="Groq",
        endpoint="https://api.groq.com/openai/v1/chat/completions",
        rate_limit="30 RPM (70B), 60 RPM (8B) — ALL FREE",
        models=[
            # ── Compound AI (Web Search built-in) ──────────────────
            Model("groq/compound",      "🆓 Groq Compound 🔥🔍⭐",     ["normal", "search"], 131072, tools=True),
            Model("groq/compound-mini", "🆓 Groq Compound Mini 🔍⭐",  ["normal", "search"], 131072, tools=True),

            # ── Production Chat ────────────────────────────────────
            Model("llama-3.3-70b-versatile", "🆓 Llama 3.3 70B ⭐",    ["normal"], 131072, tools=True),
            Model("llama-3.1-8b-instant",    "🆓 Llama 3.1 8B ⭐",     ["normal"], 131072, tools=True),

            # ── GPT-OSS Series ─────────────────────────────────────
            Model("openai/gpt-oss-120b",          "🆓 GPT-OSS 120B 🔥⭐🧠",  ["normal", "reasoning"], 131072, tools=True),
            Model("openai/gpt-oss-20b",           "🆓 GPT-OSS 20B ⭐",        ["normal"],              131072, tools=True),
            Model("openai/gpt-oss-safeguard-20b", "🆓 GPT-OSS Safeguard 20B", ["normal"],              131072),

            # ── Llama 4 (Vision + Reasoning) ───────────────────────
            Model("meta-llama/llama-4-maverick-17b-128e-instruct", "🆓 Llama 4 Maverick 👁️🧠⭐", ["normal", "reasoning"], 131072, vision=True, tools=True),
            Model("meta-llama/llama-4-scout-17b-16e-instruct",     "🆓 Llama 4 Scout 👁️⭐",      ["normal"],              131072, vision=True, tools=True),

            # ── Qwen / Moonshot ────────────────────────────────────
            Model("qwen/qwen3-32b",                   "🆓 Qwen 3 32B 🧠⭐",  ["normal", "reasoning"], 131072, tools=True),
            Model("moonshotai/kimi-k2-instruct-0905",  "🆓 Kimi K2 0905 ⭐",   ["normal"],              131072, tools=True),
            Model("moonshotai/kimi-k2-instruct",       "🆓 Kimi K2 ⭐",        ["normal"],              131072, tools=True),

            # ── Arabic ─────────────────────────────────────────────
            Model("allam-2-7b", "🆓 ALLaM 2 7B", ["normal"], 8192),

            # ── Safety / Guard ─────────────────────────────────────
            Model("meta-llama/llama-guard-4-12b",        "🆓 Llama Guard 4 12B 🛡️",   ["normal"], 131072),
            Model("meta-llama/llama-prompt-guard-2-86m",  "🆓 Prompt Guard 86M 🛡️",    ["normal"], 131072),
            Model("meta-llama/llama-prompt-guard-2-22m",  "🆓 Prompt Guard 22M 🛡️",    ["normal"], 131072),

            # ── Audio ──────────────────────────────────────────────
            Model("whisper-large-v3",       "🆓 Whisper V3",       ["audio"]),
            Model("whisper-large-v3-turbo", "🆓 Whisper V3 Turbo", ["audio"]),
        ]
    ),

    # ==================== MISTRAL ====================
    # ⚠️ FREE EXPERIMENT PLAN — 1B tokens/month, no credit card
    # Docs: https://console.mistral.ai/models
    # Verified: curl api.mistral.ai/v1/models — 45 models (function_calling)
    "mistral": Provider(
        name="Mistral",
        endpoint="https://api.mistral.ai/v1/chat/completions",
        rate_limit="1B tokens/month FREE (Experiment plan)",
        models=[
            # ── Flagship ───────────────────────────────────────────
            Model("mistral-large-latest",   "⚠️ Mistral Large 🔥⭐",       ["normal"], 131072, tools=True),
            Model("mistral-medium-latest",  "⚠️ Mistral Medium ⭐",        ["normal"], 131072, tools=True),
            Model("mistral-small-latest",   "⚠️ Mistral Small ⭐",         ["normal"], 131072, tools=True),

            # ── Ministral (Small & Fast) ───────────────────────────
            Model("ministral-3b-latest",  "⚠️ Ministral 3B ⭐",  ["normal"], 131072, tools=True),
            Model("ministral-8b-latest",  "⚠️ Ministral 8B ⭐",  ["normal"], 131072, tools=True),
            Model("ministral-14b-latest", "⚠️ Ministral 14B ⭐", ["normal"], 131072, tools=True),

            # ── Coding ─────────────────────────────────────────────
            Model("codestral-latest",       "⚠️ Codestral 💻⭐",             ["normal"], 131072, tools=True),
            Model("devstral-medium-latest", "⚠️ Devstral Medium 💻⭐",       ["normal"], 131072, tools=True),
            Model("devstral-small-latest",  "⚠️ Devstral Small 💻⭐",        ["normal"], 131072, tools=True),

            # ── Reasoning ──────────────────────────────────────────
            Model("magistral-medium-latest", "⚠️ Magistral Medium 🧠⭐", ["normal", "reasoning"], 131072, tools=True),
            Model("magistral-small-latest",  "⚠️ Magistral Small 🧠⭐",  ["normal", "reasoning"], 131072, tools=True),

            # ── Vision ─────────────────────────────────────────────
            Model("pixtral-large-latest", "⚠️ Pixtral Large 👁️⭐", ["normal"], 131072, vision=True, tools=True),

            # ── Audio ──────────────────────────────────────────────
            Model("voxtral-small-latest", "⚠️ Voxtral Small 🔊⭐", ["normal"], 131072, tools=True),

            # ── OCR ────────────────────────────────────────────────
            Model("mistral-ocr-latest", "⚠️ Mistral OCR 📄⭐", ["normal"], 131072, tools=True),

            # ── Legacy ─────────────────────────────────────────────
            Model("open-mistral-nemo", "⚠️ Mistral Nemo ⭐", ["normal"], 131072, tools=True),
        ]
    ),

    # ==================== OPENAI ====================
    # 💎 PAID ONLY — Production use, credit card required
    # Docs: https://platform.openai.com/docs/models
    # Verified: curl api.openai.com/v1/models
    "openai": Provider(
        name="OpenAI",
        endpoint="https://api.openai.com/v1/chat/completions",
        free_tier=False,
        rate_limit="Paid only — varies by tier",
        models=[
            # ── GPT-5 Series ───────────────────────────────────────
            Model("gpt-5.2-pro",  "💎 GPT-5.2 Pro 🔥⭐👁️",  ["normal"],    256000, vision=True, tools=True),
            Model("gpt-5.2",      "💎 GPT-5.2 ⭐👁️",         ["normal"],    256000, vision=True, tools=True),
            Model("gpt-5",        "💎 GPT-5 ⭐👁️",            ["normal"],    128000, vision=True, tools=True),
            Model("gpt-5-mini",   "💎 GPT-5 Mini ⭐👁️",       ["normal"],    128000, vision=True, tools=True),
            Model("gpt-5-nano",   "💎 GPT-5 Nano ⭐",          ["normal"],    128000, tools=True),

            # ── GPT-4.1 ───────────────────────────────────────────
            Model("gpt-4.1",      "💎 GPT-4.1 ⭐👁️",      ["normal"], 1000000, vision=True, tools=True),
            Model("gpt-4.1-mini", "💎 GPT-4.1 Mini ⭐👁️",  ["normal"], 1000000, vision=True, tools=True),
            Model("gpt-4.1-nano", "💎 GPT-4.1 Nano ⭐",     ["normal"], 1000000, tools=True),

            # ── Reasoning ──────────────────────────────────────────
            Model("o4-mini",  "💎 o4-mini 🧠⭐",  ["reasoning"], 200000, tools=True),
            Model("o3",       "💎 o3 🧠⭐",       ["reasoning"], 200000, tools=True),
            Model("o3-pro",   "💎 o3 Pro 🧠",     ["reasoning"], 200000),

            # ── Open Source (gpt-oss) ──────────────────────────────
            Model("gpt-oss-120b", "💎 GPT-OSS 120B 🧠⭐", ["normal", "reasoning"], 131072, tools=True),
            Model("gpt-oss-20b",  "💎 GPT-OSS 20B ⭐",    ["normal"],              131072, tools=True),
        ]
    ),

    # ==================== ANTHROPIC ====================
    # 💎 PAID ONLY — Production use, credit card required
    # Docs: https://docs.anthropic.com/claude/docs/models
    # Endpoint: /v1/messages (NOT OpenAI-compatible)
    "anthropic": Provider(
        name="Anthropic",
        endpoint="https://api.anthropic.com/v1/messages",
        auth_header="x-api-key",
        auth_prefix="",
        free_tier=False,
        rate_limit="Paid only — varies by tier",
        models=[
            # ── Claude 4.6 (Latest) ───────────────────────────────
            Model("claude-opus-4-6",   "💎 Claude Opus 4.6 🔥⭐👁️",  ["normal"], 1000000, vision=True, tools=True),
            Model("claude-sonnet-4-6", "💎 Claude Sonnet 4.6 ⭐👁️",  ["normal"], 1000000, vision=True, tools=True),

            # ── Claude 4.5 ─────────────────────────────────────────
            Model("claude-opus-4-5",   "💎 Claude Opus 4.5 ⭐👁️",   ["normal"], 200000, vision=True, tools=True),
            Model("claude-sonnet-4-5", "💎 Claude Sonnet 4.5 🧠⭐👁️",["normal", "reasoning"], 200000, vision=True, tools=True),

            # ── Claude 3.5 ─────────────────────────────────────────
            Model("claude-3-5-haiku",  "💎 Claude Haiku 3.5 ⭐",     ["normal"], 200000, tools=True),
            Model("claude-3-5-sonnet", "💎 Claude 3.5 Sonnet ⭐👁️", ["normal"], 200000, vision=True, tools=True),
        ]
    ),

    # ==================== XAI (GROK) ====================
    # 💎 PAID ONLY — Production use
    # Docs: https://api.x.ai/docs
    # Verified: curl api.x.ai/v1/models
    "xai": Provider(
        name="xAI",
        endpoint="https://api.x.ai/v1/chat/completions",
        free_tier=False,
        rate_limit="Paid only — varies by tier",
        models=[
            # ── Grok 4 Series ──────────────────────────────────────
            Model("grok-4-1",       "💎 Grok 4.1 🔥⭐",        ["normal"], 2000000, tools=True),
            Model("grok-4-1-fast",  "💎 Grok 4.1 Fast ⭐",     ["normal"], 2000000, tools=True),
            Model("grok-4",         "💎 Grok 4 ⭐",             ["normal"], 131072,  tools=True),
            Model("grok-code-fast-1","💎 Grok Code Fast 💻⭐",  ["normal"], 131072,  tools=True),

            # ── Grok 3 Series ──────────────────────────────────────
            Model("grok-3",       "💎 Grok 3 ⭐",      ["normal"], 131072, tools=True),
            Model("grok-3-mini",  "💎 Grok 3 Mini 🧠", ["reasoning"], 131072),
        ]
    ),

    # ==================== OPENROUTER ====================
    # Docs: https://openrouter.ai/models
    # Rate: 20 RPM, 200 RPD (free tier)
    # Verified: curl openrouter.ai/api/v1/models — 250+ models
    "openrouter": Provider(
        name="OpenRouter",
        endpoint="https://openrouter.ai/api/v1/chat/completions",
        rate_limit="20 RPM, 200 RPD (free models)",
        models=[
            # ── Auto Routers ───────────────────────────────────────
            Model("openrouter/free",          "🆓 Auto Router 🔥⭐👁️🧠",  ["normal", "reasoning"], 200000, vision=True, tools=True),
            Model("openrouter/optimus-alpha", "🆓 Optimus Alpha 🔥⭐",     ["normal"],              1000000, tools=True),
            Model("openrouter/quasar-alpha",  "🆓 Quasar Alpha ⭐",        ["normal"],              1000000, tools=True),

            # ── FREE: OpenAI OSS ───────────────────────────────────
            Model("openai/gpt-oss-120b:free", "🆓 GPT-OSS 120B 🔥⭐🧠",  ["normal", "reasoning"], 131072, tools=True),
            Model("openai/gpt-oss-20b:free",  "🆓 GPT-OSS 20B ⭐",        ["normal"],              131072, tools=True),

            # ── FREE: Google ───────────────────────────────────────
            Model("google/gemma-3-27b-it:free",  "🆓 Gemma 3 27B ⭐",     ["normal"], 131072, tools=True),
            Model("google/gemma-3-12b-it:free",  "🆓 Gemma 3 12B",        ["normal"], 131072),
            Model("google/gemma-3-4b-it:free",   "🆓 Gemma 3 4B",         ["normal"], 131072),
            Model("google/gemma-3n-e4b-it:free", "🆓 Gemma 3n E4B",       ["normal"], 131072),
            Model("google/gemma-3n-e2b-it:free", "🆓 Gemma 3n E2B",       ["normal"], 131072),

            # ── FREE: Meta Llama ───────────────────────────────────
            Model("meta-llama/llama-4-maverick:free",        "🆓 Llama 4 Maverick ⭐👁️🧠", ["normal", "reasoning"], 131072, vision=True, tools=True),
            Model("meta-llama/llama-4-scout:free",           "🆓 Llama 4 Scout ⭐👁️🧠",    ["normal", "reasoning"], 131072, vision=True, tools=True),
            Model("meta-llama/llama-3.3-70b-instruct:free",  "🆓 Llama 3.3 70B ⭐",         ["normal"],              131072, tools=True),
            Model("meta-llama/llama-3.2-3b-instruct:free",   "🆓 Llama 3.2 3B",             ["normal"],              131072),

            # ── FREE: DeepSeek ─────────────────────────────────────
            Model("deepseek/deepseek-chat-v3-0324:free", "🆓 DeepSeek Chat V3 ⭐", ["normal"],    64000, tools=True),
            Model("deepseek/deepseek-r1:free",           "🆓 DeepSeek R1 🧠",      ["reasoning"], 64000),
            Model("deepseek/deepseek-r1-zero:free",      "🆓 DeepSeek R1 Zero 🧠", ["reasoning"], 64000),

            # ── FREE: Qwen ─────────────────────────────────────────
            Model("qwen/qwen3-coder:free",   "🆓 Qwen3 Coder 480B 🔥⭐🧠", ["normal", "reasoning"], 262144, tools=True),
            Model("qwen/qwen3-4b:free",      "🆓 Qwen3 4B",                 ["normal"],              32768),
            Model("qwen/qwen3-next-80b-a3b-instruct:free", "🆓 Qwen3 Next 80B", ["normal"],          131072),

            # ── FREE: Mistral ──────────────────────────────────────
            Model("mistralai/mistral-small-3.1-24b-instruct:free", "🆓 Mistral Small 3.1 ⭐", ["normal"], 32768, tools=True),

            # ── FREE: NVIDIA ───────────────────────────────────────
            Model("nvidia/nemotron-3-nano-30b-a3b:free",        "🆓 Nemotron 3 Nano 30B ⭐",  ["normal"], 256000, tools=True),
            Model("nvidia/llama-3.1-nemotron-nano-8b-v1:free",  "🆓 Nemotron Nano 8B ⭐",     ["normal"], 131072, tools=True),
            Model("nvidia/nemotron-nano-12b-v2-vl:free",        "🆓 Nemotron 12B VL 👁️",     ["normal"], 128000, vision=True),
            Model("nvidia/nemotron-nano-9b-v2:free",            "🆓 Nemotron Nano 9B",         ["normal"], 131072),

            # ── FREE: Others ───────────────────────────────────────
            Model("nousresearch/hermes-3-llama-3.1-405b:free",  "🆓 Hermes 3 405B 🔥",    ["normal"], 131072),
            Model("z-ai/glm-4.5-air:free",                     "🆓 GLM 4.5 Air ⭐🧠",    ["normal", "reasoning"], 128000, tools=True),
            Model("stepfun/step-3.5-flash:free",                "🆓 Step 3.5 Flash ⭐🧠", ["normal", "reasoning"], 256000, tools=True),
            Model("upstage/solar-pro-3:free",                   "🆓 Solar Pro 3",          ["normal"], 131072),
            Model("minimax/minimax-m2.1:free",                  "🆓 MiniMax M2.1 ⭐",     ["normal"], 1000000, tools=True),
            Model("arcee-ai/trinity-large-preview:free",        "🆓 Trinity Large ⭐",    ["normal"], 128000, tools=True),
            Model("arcee-ai/trinity-mini:free",                 "🆓 Trinity Mini",         ["normal"], 128000),
            Model("liquid/lfm-2.5-1.2b-thinking:free",          "🆓 LFM Thinking 🧠",    ["reasoning"], 32768),
            Model("liquid/lfm-2.5-1.2b-instruct:free",          "🆓 LFM Instruct",        ["normal"], 32768),
            Model("cognitivecomputations/dolphin-mistral-24b-venice-edition:free", "🆓 Dolphin 24B 🔓", ["normal"], 32768),
            Model("moonshotai/kimi-vl-a3b-thinking:free",       "🆓 Kimi VL Thinking 👁️🧠", ["reasoning"], 128000, vision=True),
            Model("nousresearch/deephermes-3-llama-3-8b-preview:free", "🆓 DeepHermes 3 8B", ["normal"], 131072),

            # ── PREMIUM: Flagships ─────────────────────────────────
            Model("openai/gpt-5.2-pro",          "💎 GPT-5.2 Pro ⭐👁️",       ["normal"],              256000, vision=True, tools=True),
            Model("openai/gpt-5",                "💎 GPT-5 ⭐👁️",             ["normal"],              128000, vision=True, tools=True),
            Model("anthropic/claude-opus-4.6",   "💎 Claude Opus 4.6 ⭐👁️",   ["normal"],              1000000, vision=True, tools=True),
            Model("anthropic/claude-sonnet-4.6", "💎 Claude Sonnet 4.6 ⭐👁️", ["normal"],              1000000, vision=True, tools=True),
            Model("anthropic/claude-sonnet-4.5", "💎 Claude Sonnet 4.5 🧠👁️", ["normal", "reasoning"], 200000, vision=True),
            Model("google/gemini-3-pro-preview", "💎 Gemini 3 Pro 👁️🧠⭐",   ["normal", "reasoning"], 1000000, vision=True, tools=True),
            Model("google/gemini-2.5-pro",       "💎 Gemini 2.5 Pro 🧠⭐",    ["normal", "reasoning"], 1000000, tools=True),
            Model("x-ai/grok-4.1-fast",         "💎 Grok 4.1 Fast ⭐",        ["normal"],              2000000, tools=True),
            Model("x-ai/grok-4",                "💎 Grok 4 ⭐",               ["normal"],              131072,  tools=True),
            Model("deepseek/deepseek-v3.2",     "💎 DeepSeek V3.2 ⭐",        ["normal"],              128000, tools=True),
            Model("moonshotai/kimi-k2.5",       "💎 Kimi K2.5 👁️⭐🧠",       ["normal", "reasoning"], 131072, vision=True, tools=True),
            Model("minimax/minimax-m2.5",       "💎 MiniMax M2.5 ⭐",         ["normal"],              1000000, tools=True),
        ]
    ),

    # ==================== GEMINI ====================
    # 🆓 SEMUA GRATIS via Google AI Studio — reduced quotas since Dec 2025
    # Docs: https://ai.google.dev/gemini-api/docs/models
    # Verified: curl generativelanguage.googleapis.com — 45+ models
    "gemini": Provider(
        name="Google Gemini",
        endpoint="https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        auth_header="x-goog-api-key",
        auth_prefix="",
        rate_limit="15 RPM, 1500 RPD (free tier)",
        models=[
            # ── Gemini 3.x Preview ─────────────────────────────────
            Model("gemini-3.1-pro-preview",  "🆓 Gemini 3.1 Pro Preview 🔥👁️🧠⭐", ["normal", "reasoning"], 1048576, vision=True, tools=True),
            Model("gemini-3-pro-preview",    "🆓 Gemini 3 Pro Preview 👁️🧠⭐",     ["normal", "reasoning"], 1048576, vision=True, tools=True),
            Model("gemini-3-flash-preview",  "🆓 Gemini 3 Flash Preview 👁️⭐",     ["normal"],              1048576, vision=True, tools=True),

            # ── Gemini 2.5 (Stable) ───────────────────────────────
            Model("gemini-2.5-pro",        "🆓 Gemini 2.5 Pro 🔥🧠⭐",    ["normal", "reasoning"], 1048576, tools=True),
            Model("gemini-2.5-flash",      "🆓 Gemini 2.5 Flash 🧠⭐",    ["normal", "reasoning"], 1048576, tools=True),
            Model("gemini-2.5-flash-lite", "🆓 Gemini 2.5 Flash Lite ⭐",  ["normal"],              1048576, tools=True),

            # ── Gemini 2.0 ─────────────────────────────────────────
            Model("gemini-2.0-flash",      "🆓 Gemini 2.0 Flash 👁️⭐",    ["normal"], 1048576, vision=True, tools=True),
            Model("gemini-2.0-flash-lite", "🆓 Gemini 2.0 Flash Lite",     ["normal"], 1048576),

            # ── Gemma Open Source ──────────────────────────────────
            Model("gemma-3-27b-it",   "🆓 Gemma 3 27B ⭐",  ["normal"], 131072, tools=True),
            Model("gemma-3-12b-it",   "🆓 Gemma 3 12B",     ["normal"], 131072),
            Model("gemma-3-4b-it",    "🆓 Gemma 3 4B",      ["normal"], 131072),
            Model("gemma-3n-e4b-it",  "🆓 Gemma 3n E4B 📱", ["normal"], 131072),
            Model("gemma-3n-e2b-it",  "🆓 Gemma 3n E2B 📱", ["normal"], 131072),
        ]
    ),

    # ==================== CEREBRAS ====================
    # ⚠️ 30 RPM, 1M tokens/day FREE
    # Docs: https://inference-docs.cerebras.ai/introduction
    # Note: llama-3.3-70b & qwen-3-32b DEPRECATED 16 Feb 2026
    "cerebras": Provider(
        name="Cerebras",
        endpoint="https://api.cerebras.ai/v1/chat/completions",
        rate_limit="30 RPM, 1M tokens/day (free tier)",
        models=[
            Model("zai-glm-4.7",                    "⚠️ Z.ai GLM 4.7 🔥⭐🧠",       ["normal", "reasoning"], 128000, tools=True),
            Model("gpt-oss-120b",                   "⚠️ GPT-OSS 120B 🔥⭐🧠",       ["normal", "reasoning"], 131072, tools=True),
            Model("llama3.1-8b",                    "⚠️ Llama 3.1 8B ⭐",            ["normal"],              128000, tools=True),
            Model("qwen-3-235b-a22b-instruct-2507", "⚠️ Qwen 3 235B Instruct ⭐🧠", ["normal", "reasoning"], 262144, tools=True),
        ]
    ),

    # ==================== SAMBANOVA ====================
    # ⚠️ $5 FREE CREDIT (expire 30 hari), then free tier ketat
    # Docs: https://community.sambanova.ai/t/supported-models
    # Verified: curl api.sambanova.ai/v1/models — 18 models
    "sambanova": Provider(
        name="SambaNova",
        endpoint="https://api.sambanova.ai/v1/chat/completions",
        rate_limit="$5 free credit (30 days), then rate-limited free tier",
        models=[
            # ── Meta Llama ─────────────────────────────────────────
            Model("Meta-Llama-3.1-8B-Instruct",           "⚠️ Llama 3.1 8B ⭐",       ["normal"], 8192,   tools=True),
            Model("Meta-Llama-3.3-70B-Instruct",          "⚠️ Llama 3.3 70B ⭐",      ["normal"], 131072, tools=True),
            Model("Llama-4-Maverick-17B-128E-Instruct",   "⚠️ Llama 4 Maverick ⭐👁️", ["normal"], 131072, vision=True, tools=True),
            Model("Llama-3.3-Swallow-70B-Instruct-v0.4",  "⚠️ Llama Swallow 70B",     ["normal"], 131072),

            # ── DeepSeek ───────────────────────────────────────────
            Model("DeepSeek-R1-0528",             "⚠️ DeepSeek R1 0528 🧠",       ["reasoning"],  16384),
            Model("DeepSeek-R1-Distill-Llama-70B","⚠️ DeepSeek R1 Distill 70B 🧠",["reasoning"],  131072),
            Model("DeepSeek-V3-0324",             "⚠️ DeepSeek V3 0324 ⭐",       ["normal"],     8192,   tools=True),
            Model("DeepSeek-V3.1",                "⚠️ DeepSeek V3.1 ⭐",          ["normal"],     8192,   tools=True),
            Model("DeepSeek-V3.1-Terminus",       "⚠️ DeepSeek V3.1 Terminus ⭐", ["normal"],     8192,   tools=True),
            Model("DeepSeek-V3.1-cb",             "⚠️ DeepSeek V3.1 CB",          ["normal"],     8192),
            Model("DeepSeek-V3.2",                "⚠️ DeepSeek V3.2 🔥⭐",        ["normal"],     8192,   tools=True),

            # ── Qwen ───────────────────────────────────────────────
            Model("Qwen3-235B", "⚠️ Qwen 3 235B 🔥⭐🧠", ["normal", "reasoning"], 32768, tools=True),
            Model("Qwen3-32B",  "⚠️ Qwen 3 32B ⭐🧠",    ["normal", "reasoning"], 32768, tools=True),

            # ── GPT-OSS ────────────────────────────────────────────
            Model("gpt-oss-120b", "⚠️ GPT-OSS 120B 🔥⭐🧠", ["normal", "reasoning"], 131072, tools=True),

            # ── Others ─────────────────────────────────────────────
            Model("MiniMax-M2.5",              "⚠️ MiniMax M2.5 ⭐",  ["normal"], 197000, tools=True),
            Model("ALLaM-7B-Instruct-preview", "⚠️ ALLaM 7B",        ["normal"], 8192),

            # ── Audio / Embedding ──────────────────────────────────
            Model("Whisper-Large-v3",        "⚠️ Whisper V3",        ["audio"]),
            Model("E5-Mistral-7B-Instruct",  "⚠️ E5 Mistral 7B 📊", ["normal"]),
        ]
    ),

    # ==================== NVIDIA NIM ====================
    # ⚠️ FREE TIER — unlimited prototyping via hosted DGX Cloud
    # Docs: https://build.nvidia.com/explore/discover
    # Verified: curl integrate.api.nvidia.com/v1/models — 160+ models
    "nvidia": Provider(
        name="NVIDIA NIM",
        endpoint="https://integrate.api.nvidia.com/v1/chat/completions",
        rate_limit="Free tier (unlimited prototyping, rate-limited)",
        models=[
            # ── GPT-OSS ────────────────────────────────────────────
            Model("openai/gpt-oss-120b", "⚠️ GPT-OSS 120B 🔥⭐🧠", ["normal", "reasoning"], 131072, tools=True),
            Model("openai/gpt-oss-20b",  "⚠️ GPT-OSS 20B ⭐",       ["normal"],              131072, tools=True),

            # ── NVIDIA Nemotron ────────────────────────────────────
            Model("nvidia/llama-3.1-nemotron-ultra-253b-v1",  "⚠️ Nemotron Ultra 253B 🔥⭐🧠",   ["normal", "reasoning"], 131072, tools=True),
            Model("nvidia/llama-3.3-nemotron-super-49b-v1",   "⚠️ Nemotron Super 49B 🔥⭐🧠",    ["normal", "reasoning"], 131072, tools=True),
            Model("nvidia/llama-3.3-nemotron-super-49b-v1.5", "⚠️ Nemotron Super 49B v1.5 ⭐🧠", ["normal", "reasoning"], 131072, tools=True),
            Model("nvidia/llama-3.1-nemotron-nano-8b-v1",     "⚠️ Nemotron Nano 8B ⭐🧠",        ["normal", "reasoning"], 131072, tools=True),
            Model("nvidia/llama-3.1-nemotron-70b-instruct",   "⚠️ Nemotron 70B ⭐",               ["normal"],              131072, tools=True),
            Model("nvidia/nemotron-nano-12b-v2-vl",           "⚠️ Nemotron 12B VL 👁️🧠",        ["normal", "reasoning"], 128000, vision=True),
            Model("nvidia/nvidia-nemotron-nano-9b-v2",        "⚠️ Nemotron 9B v2",                ["normal"],              131072),
            Model("nvidia/nemotron-3-nano-30b-a3b",           "⚠️ Nemotron 3 Nano 30B ⭐",        ["normal"],              256000, tools=True),

            # ── Qwen ───────────────────────────────────────────────
            Model("qwen/qwen3-235b-a22b",                "⚠️ Qwen 3 235B 🔥⭐🧠",      ["normal", "reasoning"], 131072, tools=True),
            Model("qwen/qwen3.5-397b-a17b",              "⚠️ Qwen 3.5 397B 🔥⭐",       ["normal"],              131072, tools=True),
            Model("qwen/qwen3-coder-480b-a35b-instruct", "⚠️ Qwen 3 Coder 480B 🔥⭐🧠", ["normal", "reasoning"], 262144, tools=True),
            Model("qwen/qwen3-next-80b-a3b-instruct",    "⚠️ Qwen 3 Next 80B ⭐",        ["normal"],              131072, tools=True),
            Model("qwen/qwq-32b",                        "⚠️ QwQ 32B 🧠⭐",              ["reasoning"],           40960,  tools=True),
            Model("qwen/qwen2.5-coder-32b-instruct",     "⚠️ Qwen 2.5 Coder 32B",        ["normal"],              32768),

            # ── DeepSeek ───────────────────────────────────────────
            Model("deepseek-ai/deepseek-v3.2",          "⚠️ DeepSeek V3.2 🔥⭐",     ["normal"],    131072, tools=True),
            Model("deepseek-ai/deepseek-v3.1",          "⚠️ DeepSeek V3.1 ⭐",        ["normal"],    131072, tools=True),
            Model("deepseek-ai/deepseek-v3.1-terminus",  "⚠️ DeepSeek V3.1 Terminus ⭐",["normal"],   131072, tools=True),
            Model("deepseek-ai/deepseek-r1-distill-qwen-32b", "⚠️ DeepSeek R1 32B 🧠", ["reasoning"], 32768),

            # ── Meta Llama ─────────────────────────────────────────
            Model("meta/llama-4-maverick-17b-128e-instruct", "⚠️ Llama 4 Maverick 👁️⭐🧠", ["normal", "reasoning"], 131072, vision=True, tools=True),
            Model("meta/llama-4-scout-17b-16e-instruct",     "⚠️ Llama 4 Scout 👁️⭐",      ["normal"],              131072, vision=True, tools=True),
            Model("meta/llama-3.3-70b-instruct",             "⚠️ Llama 3.3 70B ⭐",          ["normal"],              131072, tools=True),
            Model("meta/llama-3.1-405b-instruct",            "⚠️ Llama 3.1 405B 🔥⭐",       ["normal"],              131072, tools=True),
            Model("meta/llama-3.1-70b-instruct",             "⚠️ Llama 3.1 70B ⭐",          ["normal"],              131072, tools=True),
            Model("meta/llama-3.1-8b-instruct",              "⚠️ Llama 3.1 8B ⭐",           ["normal"],              131072, tools=True),

            # ── Mistral ────────────────────────────────────────────
            Model("mistralai/mistral-large-3-675b-instruct-2512", "⚠️ Mistral Large 675B 🔥⭐", ["normal"], 131072, tools=True),
            Model("mistralai/mistral-medium-3-instruct",          "⚠️ Mistral Medium 3 ⭐",      ["normal"], 131072, tools=True),
            Model("mistralai/mistral-small-3.1-24b-instruct-2503","⚠️ Mistral Small 3.1 ⭐",     ["normal"], 131072, tools=True),
            Model("mistralai/mixtral-8x7b-instruct-v0.1",        "⚠️ Mixtral 8x7B ⭐",          ["normal"], 32768,  tools=True),

            # ── Moonshot ───────────────────────────────────────────
            Model("moonshotai/kimi-k2.5",              "⚠️ Kimi K2.5 👁️⭐🧠",    ["normal", "reasoning"], 131072, vision=True, tools=True),
            Model("moonshotai/kimi-k2-instruct",       "⚠️ Kimi K2 ⭐",           ["normal"],              131072, tools=True),
            Model("moonshotai/kimi-k2-instruct-0905",  "⚠️ Kimi K2 0905 ⭐",      ["normal"],              131072, tools=True),

            # ── MiniMax ────────────────────────────────────────────
            Model("minimaxai/minimax-m2.5", "⚠️ MiniMax M2.5 🔥⭐", ["normal"], 1048576, tools=True),

            # ── GLM / StepFun / Others ─────────────────────────────
            Model("z-ai/glm5",              "⚠️ GLM-5 ⭐",          ["normal"], 128000, tools=True),
            Model("z-ai/glm4.7",            "⚠️ GLM-4.7 ⭐",        ["normal"], 128000, tools=True),
            Model("stepfun-ai/step-3.5-flash","⚠️ Step 3.5 Flash ⭐", ["normal"], 256000, tools=True),

            # ── Google Gemma ───────────────────────────────────────
            Model("google/gemma-3-27b-it",  "⚠️ Gemma 3 27B",  ["normal"], 131072),
            Model("google/gemma-3n-e4b-it", "⚠️ Gemma 3n E4B", ["normal"], 131072),
        ]
    ),

    # ==================== POLLINATIONS ====================
    # 🆓 No signup needed, $1.5/week free credits
    # Verified: curl gen.pollinations.ai/models — 26 models
    "pollinations": Provider(
        name="Pollinations",
        endpoint="https://gen.pollinations.ai/v1/chat/completions",
        auth_header="Authorization",
        auth_prefix="Bearer",
        rate_limit="1/15s (anon), unlimited (sk_)",
        models=[
            # ── 🆓 Free Tier ──────────────────────────────────────
            Model("qwen-safety",  "🆓 Qwen3Guard 8B",              ["normal"]),
            Model("nova-fast",    "🆓 Amazon Nova Micro",           ["normal"]),
            Model("openai-fast",  "🆓 OpenAI GPT-5 Nano 👁️",     ["normal"], vision=True),
            Model("gemini-fast",  "🆓 Gemini 2.5 Flash Lite 👁️",  ["normal"], vision=True),
            Model("qwen-coder",   "🆓 Qwen3 Coder 30B",            ["normal"]),
            Model("mistral",      "🆓 Mistral Small 3.2 24B",      ["normal"]),
            Model("qwen-character","🆓 Qwen Character 🎭",         ["normal"]),

            # Mid Tier
            Model("openai",   "🆓 OpenAI GPT-5 Mini 👁️",  ["normal"], vision=True),
            Model("deepseek", "🆓 DeepSeek V3.2",           ["normal"]),
            Model("minimax",  "🆓 MiniMax M2.1",            ["normal"]),
            Model("kimi",     "🆓 Kimi K2.5 👁️",           ["normal"], vision=True),
            Model("glm",      "🆓 Z.ai GLM-5",              ["normal"]),

            # Search Built-in
            Model("perplexity-fast", "🆓 Perplexity Sonar 🔍",              ["search"]),
            Model("gemini-search",   "🆓 Gemini 2.5 Flash Search 🔥🔍👁️", ["search"], vision=True, tools=True),

            # Premium Features
            Model("openai-large",         "🆓 OpenAI GPT-5.2 👁️",         ["normal"],              vision=True),
            Model("perplexity-reasoning", "🆓 Perplexity Reasoning 🔍🧠",  ["reasoning", "search"]),
            Model("openai-audio",         "🆓 GPT-4o Mini Audio 👁️",      ["normal"],              vision=True),
            Model("midijourney",          "🆓 MIDIjourney 🎵",             ["normal"]),

            # ── 💎 PAID ONLY ──────────────────────────────────────
            Model("grok",          "💎 xAI Grok 4 Fast",           ["normal"]),
            Model("gemini",        "💎 Google Gemini 3 Flash 👁️", ["normal"],              vision=True),
            Model("claude-fast",   "💎 Claude Haiku 4.5 👁️",      ["normal"],              vision=True),
            Model("claude",        "💎 Claude Sonnet 4.6 👁️",     ["normal"],              vision=True),
            Model("claude-large",  "💎 Claude Opus 4.6 👁️",       ["normal"],              vision=True),
            Model("gemini-large",  "💎 Gemini 3 Pro 👁️🧠",        ["normal", "reasoning"], vision=True),

            # ── 🤖 Agents ─────────────────────────────────────────
            Model("nomnom", "🆓 NomNom 🔍🧠",       ["reasoning", "search"]),
            Model("polly",  "🆓 Polly 🔥🔍👁️🧠",  ["normal", "reasoning", "search"], vision=True),
        ]
    ),

    # ==================== CLOUDFLARE ====================
    # ⚠️ 10K NEURONS/DAY FREE
    # Docs: https://developers.cloudflare.com/workers-ai/models/
    # Verified: curl api.cloudflare.com/.../ai/models/search — 70+ models
    "cloudflare": Provider(
        name="Cloudflare",
        endpoint="https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}",
        rate_limit="10K neurons/day (free tier)",
        models=[
            # ── LLM Chat + Tools ───────────────────────────────────
            Model("@cf/meta/llama-3.3-70b-instruct-fp8-fast",  "⚠️ Llama 3.3 70B ⭐",     ["normal"], 131072, tools=True),
            Model("@cf/meta/llama-3.1-8b-instruct",            "⚠️ Llama 3.1 8B ⭐",      ["normal"], 131072, tools=True),
            Model("@cf/meta/llama-3.1-8b-instruct-fp8",        "⚠️ Llama 3.1 8B FP8 ⭐",  ["normal"], 131072, tools=True),
            Model("@cf/meta/llama-4-scout-17b-16e-instruct",   "⚠️ Llama 4 Scout 🧠⭐",   ["normal", "reasoning"], 131072, tools=True),
            Model("@cf/mistralai/mistral-small-3.1-24b-instruct","⚠️ Mistral Small 3.1 ⭐", ["normal"], 32768, tools=True),
            Model("@cf/qwen/qwen2.5-coder-32b-instruct",       "⚠️ Qwen 2.5 Coder 32B ⭐",["normal"], 32768, tools=True),
            Model("@cf/qwen/qwen3-30b-a3b-fp8",                "⚠️ Qwen 3 30B ⭐",        ["normal"], 32768, tools=True),
            Model("@cf/zai-org/glm-4.7-flash",                 "⚠️ GLM 4.7 Flash ⭐",     ["normal"], 131072, tools=True),
            Model("@cf/ibm-granite/granite-4.0-h-micro",       "⚠️ Granite 4.0 Micro",    ["normal"], 131072),

            # ── GPT-OSS ────────────────────────────────────────────
            Model("@cf/openai/gpt-oss-120b", "⚠️ GPT-OSS 120B 🔥⭐🧠", ["normal", "reasoning"], 131072, tools=True),
            Model("@cf/openai/gpt-oss-20b",  "⚠️ GPT-OSS 20B ⭐",       ["normal"],              131072, tools=True),

            # ── Vision ─────────────────────────────────────────────
            Model("@cf/meta/llama-3.2-11b-vision-instruct", "⚠️ Llama 3.2 Vision 👁️", ["normal"], 131072, vision=True),
            Model("@cf/llava-hf/llava-1.5-7b-hf",          "⚠️ LLaVA 1.5 7B 👁️",     ["normal"], 4096,   vision=True),

            # ── Reasoning ──────────────────────────────────────────
            Model("@cf/deepseek-ai/deepseek-r1-distill-qwen-32b", "⚠️ DeepSeek R1 32B 🧠", ["reasoning"], 32768),
            Model("@cf/qwen/qwq-32b",                              "⚠️ QwQ 32B 🧠",         ["reasoning"], 32768),

            # ── Smaller Chat ───────────────────────────────────────
            Model("@cf/google/gemma-3-12b-it",          "⚠️ Gemma 3 12B",     ["normal"], 131072),
            Model("@cf/meta/llama-3.2-3b-instruct",     "⚠️ Llama 3.2 3B",    ["normal"], 131072),
            Model("@cf/meta/llama-3.2-1b-instruct",     "⚠️ Llama 3.2 1B",    ["normal"], 131072),
            Model("@cf/meta/llama-3-8b-instruct",       "⚠️ Llama 3 8B ⭐",   ["normal"], 8192, tools=True),

            # ── Audio ──────────────────────────────────────────────
            Model("@cf/openai/whisper-large-v3-turbo", "⚠️ Whisper V3 Turbo", ["audio"]),
            Model("@cf/openai/whisper",                "⚠️ Whisper",          ["audio"]),
            Model("@cf/deepgram/nova-3",               "⚠️ Deepgram Nova 3",  ["audio"]),

            # ── Image Generation ───────────────────────────────────
            Model("@cf/black-forest-labs/flux-2-dev",       "⚠️ FLUX 2 Dev 🎨",    ["normal"]),
            Model("@cf/black-forest-labs/flux-1-schnell",   "⚠️ FLUX 1 Schnell 🎨", ["normal"]),

            # ── Embedding ──────────────────────────────────────────
            Model("@cf/baai/bge-m3",           "⚠️ BGE M3 📊",        ["normal"]),
            Model("@cf/baai/bge-large-en-v1.5","⚠️ BGE Large EN 📊",  ["normal"]),
        ]
    ),

    # ==================== HUGGINGFACE ====================
    # Mixed: Small models free via Serverless, large need HF credits
    # Docs: https://huggingface.co/docs/api-inference
    # Verified: curl huggingface.co/api/models?inference=warm — 50 models
    "huggingface": Provider(
        name="HuggingFace",
        endpoint="https://router.huggingface.co/v1/chat/completions",
        rate_limit="~50 calls/day (free serverless), credit-based (large models)",
        models=[
            # ── 🆓 Gratis via Serverless (model kecil) ────────────
            Model("mistralai/Mistral-7B-Instruct-v0.3", "🆓 Mistral 7B",  ["normal"], 32768),
            Model("HuggingFaceH4/zephyr-7b-beta",       "🆓 Zephyr 7B",   ["normal"], 32768),

            # ── 💎 Via Inference Providers (pakai HF credit) ──────
            Model("meta-llama/Llama-3.3-70B-Instruct",     "💎 Llama 3.3 70B ⭐",       ["normal"],              131072, tools=True),
            Model("meta-llama/Meta-Llama-3.1-8B-Instruct", "💎 Llama 3.1 8B",           ["normal"],              131072),
            Model("Qwen/Qwen3-235B-A22B",                  "💎 Qwen 3 235B 🧠⭐",       ["normal", "reasoning"], 131072, tools=True),
            Model("Qwen/Qwen3.5-397B-A17B",                "💎 Qwen 3.5 397B 🔥⭐",     ["normal"],              131072, tools=True),
            Model("Qwen/Qwen3.5-35B-A3B",                  "💎 Qwen 3.5 35B",           ["normal"],              131072),
            Model("Qwen/QwQ-32B",                           "💎 QwQ 32B 🧠",             ["reasoning"],           32768),
            Model("deepseek-ai/DeepSeek-R1",               "💎 DeepSeek R1 🧠",          ["reasoning"],           131072),
            Model("deepseek-ai/DeepSeek-R1-0528",          "💎 DeepSeek R1 0528 🧠",     ["reasoning"],           131072),
            Model("deepseek-ai/DeepSeek-V3.2",             "💎 DeepSeek V3.2 ⭐",        ["normal"],              131072, tools=True),
            Model("deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",   "💎 DeepSeek R1 7B 🧠",  ["reasoning"],           32768),
            Model("deepseek-ai/DeepSeek-R1-Distill-Llama-70B", "💎 DeepSeek R1 70B 🧠",  ["reasoning"],           131072),
            Model("google/gemma-3-27b-it",                  "💎 Gemma 3 27B",             ["normal"],              131072),
            Model("openai/gpt-oss-120b",                    "💎 GPT-OSS 120B 🧠⭐",      ["normal", "reasoning"], 131072, tools=True),
            Model("openai/gpt-oss-20b",                     "💎 GPT-OSS 20B",             ["normal"],              131072),
        ]
    ),

    # ==================== COHERE ====================
    # ⚠️ 1000 REQ/MONTH FREE (Trial key, no credit card)
    # Docs: https://docs.cohere.com/v2/docs/models
    # Verified: curl api.cohere.com/v1/models — 20 models
    "cohere": Provider(
        name="Cohere",
        endpoint="https://api.cohere.ai/v2/chat",
        rate_limit="1000 calls/month (trial key)",
        models=[
            # ── Chat + Tools ───────────────────────────────────────
            Model("command-a-vision-07-2025",    "⚠️ Command A Vision 🔥👁️⭐", ["normal"],              256000, vision=True, tools=True),
            Model("command-a-reasoning-08-2025", "⚠️ Command A Reasoning 🧠⭐", ["normal", "reasoning"], 256000, tools=True),
            Model("command-r-plus-08-2024",      "⚠️ Command R+ 🔍⭐",          ["normal", "search"],    128000, tools=True),
            Model("command-r-08-2024",           "⚠️ Command R ⭐",             ["normal"],              128000, tools=True),
            Model("command-r7b-12-2024",         "⚠️ Command R 7B ⭐",          ["normal"],              128000, tools=True),
            Model("command-r7b-arabic-02-2025",  "⚠️ Command R 7B Arabic ⭐",   ["normal"],              128000, tools=True),

            # ── Multilingual (Aya) ─────────────────────────────────
            Model("c4ai-aya-vision-8b",    "⚠️ Aya Vision 8B 👁️",   ["normal"], 8192, vision=True),
            Model("c4ai-aya-expanse-32b",  "⚠️ Aya Expanse 32B",     ["normal"], 128000),
            Model("c4ai-aya-expanse-8b",   "⚠️ Aya Expanse 8B",      ["normal"], 8192),

            # ── Embedding ──────────────────────────────────────────
            Model("embed-v4.0",                        "⚠️ Embed V4 📊",               ["normal"]),
            Model("embed-english-v3.0",                "⚠️ Embed EN V3 📊",             ["normal"]),
            Model("embed-multilingual-v2.0",           "⚠️ Embed Multilingual V2 📊",   ["normal"]),
            Model("embed-english-v3.0-image",          "⚠️ Embed EN V3 Image 📊",       ["normal"]),
            Model("embed-multilingual-light-v3.0-image","⚠️ Embed Multi Light Image 📊", ["normal"]),

            # ── Rerank ─────────────────────────────────────────────
            Model("rerank-v4.0-pro",           "⚠️ Rerank V4 Pro 🔍",        ["normal"]),
            Model("rerank-v4.0-fast",          "⚠️ Rerank V4 Fast 🔍",       ["normal"]),
            Model("rerank-multilingual-v3.0",  "⚠️ Rerank Multi V3 🔍",      ["normal"]),
        ]
    ),

    # ==================== SILICONFLOW ====================
    # Mixed: Some free, most paid (very cheap pricing)
    # Docs: https://docs.siliconflow.cn/en/api-reference
    # ⚠️ Domain: api.siliconflow.COM (bukan .cn!)
    # Verified: curl api.siliconflow.com/v1/models — 90+ models
    "siliconflow": Provider(
        name="SiliconFlow",
        endpoint="https://api.siliconflow.com/v1/chat/completions",
        rate_limit="100 RPD (free models), varies (paid)",
        models=[
            # ── 🆓 FREE Models ────────────────────────────────────
            Model("Qwen/Qwen2.5-7B-Instruct",              "🆓 Qwen 2.5 7B",               ["normal"],    32768),
            Model("Qwen/Qwen2.5-Coder-7B-Instruct",        "🆓 Qwen 2.5 Coder 7B",         ["normal"],    32768),
            Model("THUDM/GLM-4-9B-0414",                   "🆓 GLM 4 9B",                   ["normal"],    128000),
            Model("THUDM/GLM-Z1-9B-0414",                  "🆓 GLM Z1 9B 🧠",              ["reasoning"], 128000),
            Model("deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",  "🆓 DeepSeek R1 7B 🧠",      ["reasoning"], 32768),
            Model("deepseek-ai/DeepSeek-R1-Distill-Qwen-14B", "🆓 DeepSeek R1 14B 🧠",     ["reasoning"], 32768),
            Model("deepseek-ai/DeepSeek-R1-Distill-Qwen-32B", "🆓 DeepSeek R1 32B 🧠",     ["reasoning"], 32768),
            Model("Qwen/QwQ-32B",                           "🆓 QwQ 32B 🧠",                ["reasoning"], 32768),
            Model("meta-llama/Meta-Llama-3.1-8B-Instruct",  "🆓 Llama 3.1 8B",              ["normal"],    131072),

            # ── 💎 PAID: Flagship Chat ─────────────────────────────
            Model("deepseek-ai/DeepSeek-V3.2",          "💎 DeepSeek V3.2 🔥⭐",     ["normal"],              164000, tools=True),
            Model("deepseek-ai/DeepSeek-V3.2-Exp",      "💎 DeepSeek V3.2 Exp ⭐",   ["normal"],              164000, tools=True),
            Model("deepseek-ai/DeepSeek-V3.1",          "💎 DeepSeek V3.1 ⭐",        ["normal"],              164000, tools=True),
            Model("deepseek-ai/DeepSeek-V3.1-Terminus",  "💎 DeepSeek V3.1 Terminus ⭐",["normal"],            164000, tools=True),
            Model("deepseek-ai/DeepSeek-V3",            "💎 DeepSeek V3",              ["normal"],              164000),
            Model("deepseek-ai/DeepSeek-R1",            "💎 DeepSeek R1 🧠",           ["reasoning"],           164000),
            Model("deepseek-ai/DeepSeek-R1-0528",       "💎 DeepSeek R1 0528 🧠",     ["reasoning"],           164000),

            # ── 💎 PAID: Qwen ──────────────────────────────────────
            Model("Qwen/Qwen3-235B-A22B-Instruct-2507",  "💎 Qwen 3 235B 🔥⭐🧠",  ["normal", "reasoning"], 262144, tools=True),
            Model("Qwen/Qwen3-235B-A22B-Thinking-2507",  "💎 Qwen 3 235B Think 🧠", ["reasoning"],           262144),
            Model("Qwen/Qwen3-Coder-480B-A35B-Instruct", "💎 Qwen Coder 480B 🔥⭐", ["normal"],              262144, tools=True),
            Model("Qwen/Qwen3-Coder-30B-A3B-Instruct",   "💎 Qwen Coder 30B ⭐",    ["normal"],              131072, tools=True),
            Model("Qwen/Qwen3-32B",                      "💎 Qwen 3 32B 🧠⭐",      ["normal", "reasoning"], 32768,  tools=True),
            Model("Qwen/Qwen3-14B",                      "💎 Qwen 3 14B",            ["normal"],              32768),
            Model("Qwen/Qwen3-8B",                       "💎 Qwen 3 8B 🧠⭐",       ["normal", "reasoning"], 40960,  tools=True),
            Model("Qwen/Qwen3-Next-80B-A3B-Instruct",    "💎 Qwen 3 Next 80B ⭐",   ["normal"],              131072, tools=True),
            Model("Qwen/Qwen-Image",                     "💎 Qwen Image 🎨",         ["normal"]),
            Model("Qwen/Qwen-Image-Edit",                "💎 Qwen Image Edit 🎨",    ["normal"]),

            # ── 💎 PAID: Qwen Vision ──────────────────────────────
            Model("Qwen/Qwen3-VL-235B-A22B-Instruct",    "💎 Qwen VL 235B 👁️⭐",   ["normal"],    262144, vision=True, tools=True),
            Model("Qwen/Qwen3-VL-235B-A22B-Thinking",    "💎 Qwen VL 235B Think 👁️🧠",["reasoning"], 262144, vision=True),
            Model("Qwen/Qwen3-VL-32B-Instruct",          "💎 Qwen VL 32B 👁️",      ["normal"],    131072, vision=True),
            Model("Qwen/Qwen3-VL-8B-Instruct",           "💎 Qwen VL 8B 👁️",       ["normal"],    32768,  vision=True),

            # ── 💎 PAID: Moonshot / MiniMax / GLM ──────────────────
            Model("moonshotai/Kimi-K2.5",          "💎 Kimi K2.5 👁️⭐🧠",     ["normal", "reasoning"], 262144, vision=True, tools=True),
            Model("moonshotai/Kimi-K2-Instruct",   "💎 Kimi K2 ⭐",            ["normal"],              131072, tools=True),
            Model("moonshotai/Kimi-K2-Thinking",   "💎 Kimi K2 Think 🧠",      ["reasoning"],           131072),
            Model("MiniMaxAI/MiniMax-M2.5",        "💎 MiniMax M2.5 ⭐",       ["normal"],              197000, tools=True),
            Model("MiniMaxAI/MiniMax-M2.1",        "💎 MiniMax M2.1",          ["normal"],              197000),
            Model("zai-org/GLM-5",                  "💎 GLM-5 🔥⭐",            ["normal"],              128000, tools=True),
            Model("zai-org/GLM-4.7",                "💎 GLM-4.7 ⭐",            ["normal"],              128000, tools=True),
            Model("zai-org/GLM-4.6V",               "💎 GLM-4.6V 👁️",          ["normal"],              128000, vision=True),

            # ── 💎 PAID: Baidu / ByteDance / Tencent ───────────────
            Model("baidu/ERNIE-4.5-300B-A47B",            "💎 ERNIE 4.5 300B 🔥⭐", ["normal"], 128000, tools=True),
            Model("tencent/Hunyuan-A13B-Instruct",        "💎 Hunyuan A13B",         ["normal"], 128000),
            Model("ByteDance-Seed/Seed-OSS-36B-Instruct", "💎 ByteDance Seed 36B",   ["normal"], 131072),

            # ── 💎 PAID: Omni (Audio+Vision) ───────────────────────
            Model("Qwen/Qwen3-Omni-30B-A3B-Instruct", "💎 Qwen Omni 30B 👁️🔊", ["normal"], 131072, vision=True),

            # ── 💎 PAID: Video Generation ──────────────────────────
            Model("Wan-AI/Wan2.2-T2V-A14B", "💎 Wan T2V 🎬",  ["normal"]),
            Model("Wan-AI/Wan2.2-I2V-A14B", "💎 Wan I2V 🎬",  ["normal"]),

            # ── 💎 PAID: Image Generation ──────────────────────────
            Model("black-forest-labs/FLUX.2-pro",        "💎 FLUX 2 Pro 🎨",    ["normal"]),
            Model("black-forest-labs/FLUX.1-Kontext-pro","💎 FLUX Kontext 🎨",  ["normal"]),
            Model("black-forest-labs/FLUX.1-schnell",    "💎 FLUX Schnell 🎨",  ["normal"]),

            # ── 💎 PAID: TTS ───────────────────────────────────────
            Model("fishaudio/fish-speech-1.5",      "💎 Fish Speech 🔊",  ["normal"]),
            Model("FunAudioLLM/CosyVoice2-0.5B",   "💎 CosyVoice 🔊",   ["normal"]),

            # ── 💎 PAID: Embedding & Rerank ────────────────────────
            Model("Qwen/Qwen3-Embedding-8B",  "💎 Qwen Embed 8B 📊",   ["normal"]),
            Model("Qwen/Qwen3-Reranker-8B",   "💎 Qwen Rerank 8B 🔍",  ["normal"]),
        ]
    ),

    # ==================== ROUTEWAY ====================
    # ⚠️ $1 FREE CREDIT saat daftar, 70+ model via unified API
    # Docs: https://routeway.ai/docs
    # Rate: 20 RPM, 200 RPD (free models)
    "routeway": Provider(
        name="Routeway",
        endpoint="https://api.routeway.ai/v1/chat/completions",
        rate_limit="20 RPM, 200 RPD (free models)",
        models=[
            Model("glm-4.6:free",                "🆓 GLM 4.6 🔥⭐🧠",    ["normal", "reasoning"], 200000, tools=True),
            Model("glm-4.5-air:free",            "🆓 GLM 4.5 Air",        ["normal"],              131000),
            Model("deepseek-r1:free",            "🆓 DeepSeek R1 🧠",     ["reasoning"],           164000),
            Model("minimax-m2:free",             "🆓 MiniMax M2",          ["normal"],              197000),
            Model("kimi-k2:free",                "🆓 Kimi K2 ⭐",         ["normal"],              262000, tools=True),
            Model("deepseek-v3.1:free",          "🆓 DeepSeek V3.1 ⭐",   ["normal"],              131000, tools=True),
            Model("llama-3.3-70b-instruct:free", "🆓 Llama 3.3 70B ⭐",   ["normal"],              131000, tools=True),
            Model("mistral-small-3:free",        "🆓 Mistral Small 3 ⭐",  ["normal"],              32768,  tools=True),
        ]
    ),

    # ==================== MLVOCA ====================
    # 🆓 No API key required, unlimited, model kecil saja
    "mlvoca": Provider(
        name="MLVOCA",
        endpoint="https://mlvoca.com/api/generate",
        auth_header="",
        auth_prefix="",
        rate_limit="unlimited",
        models=[
            Model("tinyllama",        "🆓 TinyLlama",            ["normal"]),
            Model("deepseek-r1:1.5b", "🆓 DeepSeek R1 1.5B 🧠", ["reasoning"]),
        ]
    ),

    # ==================== PUTER ====================
    # 🆓 User-pays model — developer gratis, user pakai akun Puter sendiri
    # Docs: https://docs.puter.com/AI/chat/
    # Note: 500+ model tersedia, tidak perlu API key developer
    "puter": Provider(
        name="Puter",
        endpoint="https://api.puter.com/drivers/call",
        rate_limit="Free Tier (Puter.com) — User-Pays",
        models=[
            # ── OpenAI ─────────────────────────────────────────────
            Model("gpt-5-nano",  "🆓 GPT-5 Nano 👁️⭐",  ["normal"], 128000, vision=True, tools=True),
            Model("gpt-5-mini",  "🆓 GPT-5 Mini 👁️⭐",  ["normal"], 128000, vision=True, tools=True),
            Model("gpt-4.1-nano","🆓 GPT-4.1 Nano ⭐",   ["normal"], 128000, tools=True),

            # ── Anthropic ──────────────────────────────────────────
            Model("claude-sonnet-4-5","🆓 Claude Sonnet 4.5 🔥🧠", ["normal", "reasoning"], 200000),
            Model("claude-3-5-sonnet","🆓 Claude 3.5 Sonnet 🧠",   ["normal", "reasoning"], 200000),

            # ── Google ─────────────────────────────────────────────
            Model("google/gemini-2.5-flash",   "🆓 Gemini 2.5 Flash 🧠⭐",    ["normal", "reasoning"], 1048576, tools=True),
            Model("google/gemini-2.5-pro",     "🆓 Gemini 2.5 Pro 🔥🧠⭐",   ["normal", "reasoning"], 1048576, tools=True),
            Model("gemini-2.5-flash-lite",     "🆓 Gemini 2.5 Flash Lite ⭐",  ["normal"],              1048576, tools=True),

            # ── DeepSeek ───────────────────────────────────────────
            Model("deepseek/deepseek-r1",   "🆓 DeepSeek R1 🧠",  ["reasoning"], 128000),
            Model("deepseek/deepseek-chat", "🆓 DeepSeek V3 ⭐",  ["normal"],    128000, tools=True),

            # ── xAI Grok ───────────────────────────────────────────
            Model("x-ai/grok-4-1-fast", "🆓 Grok 4.1 Fast 🔥⭐", ["normal"], 131072, tools=True),
            Model("x-ai/grok-4-1-mini", "🆓 Grok 4.1 Mini ⭐",   ["normal"], 131072, tools=True),

            # ── Meta ───────────────────────────────────────────────
            Model("meta-llama/llama-3.3-70b-instruct", "🆓 Llama 3.3 70B ⭐", ["normal"], 131072, tools=True),

            # ── Perplexity ─────────────────────────────────────────
            Model("perplexity/sonar",     "🆓 Perplexity Sonar 🔍",       ["search"], 128000),
            Model("perplexity/sonar-pro", "🆓 Perplexity Sonar Pro 🔥🔍", ["search"], 200000),
        ]
    ),
}

# ============================================================
# SEARCH PROVIDERS
# ============================================================

SEARCH_PROVIDERS = {
    "duckduckgo": {
        "name": "DuckDuckGo",
        "type": "library",
        "rate_limit": "unlimited",
        "requires_key": False,
    },
    "tavily": {
        "name": "Tavily",
        "endpoint": "https://api.tavily.com/search",
        "rate_limit": "1000/month",
        "requires_key": True,
    },
    "brave": {
        "name": "Brave",
        "endpoint": "https://api.search.brave.com/res/v1/web/search",
        "rate_limit": "2000/month",
        "requires_key": True,
    },
    "serper": {
        "name": "Serper",
        "endpoint": "https://google.serper.dev/search",
        "rate_limit": "2500 one-time",
        "requires_key": True,
    },
    "jina": {
        "name": "Jina",
        "endpoint": "https://s.jina.ai/{query}",
        "rate_limit": "rate limited",
        "requires_key": False,
    },
}

# ============================================================
# FALLBACK CHAINS — Updated with verified model IDs
# ============================================================

FALLBACK_CHAINS = {
    "normal": [
        ("groq",        "llama-3.3-70b-versatile"),
        ("groq",        "llama-3.1-8b-instant"),
        ("mistral",     "mistral-small-latest"),
        ("cerebras",    "llama3.1-8b"),
        ("nvidia",      "meta/llama-3.3-70b-instruct"),
        ("nvidia",      "deepseek-ai/deepseek-v3.2"),
        ("sambanova",   "Meta-Llama-3.3-70B-Instruct"),
        ("sambanova",   "DeepSeek-V3.2"),
        ("openrouter",  "openrouter/free"),
        ("openrouter",  "meta-llama/llama-3.3-70b-instruct:free"),
        ("openrouter",  "deepseek/deepseek-chat-v3-0324:free"),
        ("cloudflare",  "@cf/meta/llama-3.3-70b-instruct-fp8-fast"),
        ("cloudflare",  "@cf/meta/llama-3.1-8b-instruct"),
        ("routeway",    "llama-3.3-70b-instruct:free"),
        ("pollinations","openai"),
        ("puter",       "gpt-5-mini"),
    ],
    "reasoning": [
        ("groq",        "openai/gpt-oss-120b"),
        ("groq",        "qwen/qwen3-32b"),
        ("cerebras",    "gpt-oss-120b"),
        ("cerebras",    "zai-glm-4.7"),
        ("nvidia",      "nvidia/llama-3.1-nemotron-ultra-253b-v1"),
        ("nvidia",      "nvidia/llama-3.3-nemotron-super-49b-v1"),
        ("nvidia",      "deepseek-ai/deepseek-r1-distill-qwen-32b"),
        ("sambanova",   "DeepSeek-R1-0528"),
        ("sambanova",   "Qwen3-235B"),
        ("openrouter",  "openrouter/free"),
        ("openrouter",  "openai/gpt-oss-120b:free"),
        ("openrouter",  "deepseek/deepseek-r1:free"),
        ("openrouter",  "qwen/qwen3-coder:free"),
        ("openrouter",  "stepfun/step-3.5-flash:free"),
        ("cloudflare",  "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b"),
        ("cloudflare",  "@cf/qwen/qwq-32b"),
        ("routeway",    "deepseek-r1:free"),
        ("pollinations","perplexity-reasoning"),
    ],
    "search": [
        ("duckduckgo",  None),
        ("tavily",      None),
        ("brave",       None),
        ("serper",      None),
        ("jina",        None),
    ],
    "vision": [
        ("groq",        "meta-llama/llama-4-maverick-17b-128e-instruct"),
        ("groq",        "meta-llama/llama-4-scout-17b-16e-instruct"),
        ("nvidia",      "meta/llama-4-maverick-17b-128e-instruct"),
        ("nvidia",      "moonshotai/kimi-k2.5"),
        ("sambanova",   "Llama-4-Maverick-17B-128E-Instruct"),
        ("openrouter",  "meta-llama/llama-4-maverick:free"),
        ("openrouter",  "moonshotai/kimi-vl-a3b-thinking:free"),
        ("cloudflare",  "@cf/meta/llama-3.2-11b-vision-instruct"),
        ("puter",       "gpt-5-nano"),
        ("pollinations","openai-fast"),
    ],
}

# ============================================================
# LAVALINK NODES (Music Servers)
# ============================================================

LAVALINK_NODES = [
    {
        "identifier": "Serenetia-V4",
        "host":        os.getenv("LAVALINK_HOST",     "lavalinkv4.serenetia.com"),
        "port":        int(os.getenv("LAVALINK_PORT", "443")),
        "password":    os.getenv("LAVALINK_PASSWORD", "https://dsc.gg/ajidevserver"),
        "secure":      os.getenv("LAVALINK_SECURE",   "true").lower() == "true",
        "heartbeat":   30,
        "retries":     3,
    }
]

GENIUS_TOKEN = os.getenv("GENIUS_API_KEY")

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_provider(name: str) -> Optional[Provider]:
    return PROVIDERS.get(name.lower())

def get_model(provider_name: str, model_id: str) -> Optional[Model]:
    provider = get_provider(provider_name)
    if provider:
        for model in provider.models:
            if model.id == model_id:
                return model
    return None

def get_models_by_mode(mode: str) -> List[tuple]:
    results = []
    for provider_name, provider in PROVIDERS.items():
        for model in provider.models:
            if mode in model.modes:
                results.append((provider_name, model))
    return results

def get_api_key(provider_name: str) -> Optional[str]:
    return API_KEYS.get(provider_name.lower())

def is_provider_available(provider_name: str) -> bool:
    provider = get_provider(provider_name)
    if not provider:
        return False
    if provider_name in ["mlvoca", "puter"]:
        return True
    if provider_name == "pollinations":
        return True
    return bool(get_api_key(provider_name))

def list_available_providers() -> List[str]:
    return [name for name in PROVIDERS.keys() if is_provider_available(name)]

def get_tools_capable_models() -> List[tuple]:
    """Return semua model yang support tool calling."""
    return [
        (provider_name, model)
        for provider_name, provider in PROVIDERS.items()
        for model in provider.models
        if model.tools
    ]

def get_vision_capable_models() -> List[tuple]:
    """Return semua model yang support vision/image."""
    return [
        (provider_name, model)
        for provider_name, provider in PROVIDERS.items()
        for model in provider.models
        if model.vision
    ]

def get_free_models() -> List[tuple]:
    """Return semua model gratis (🆓 atau ⚠️)."""
    return [
        (provider_name, model)
        for provider_name, provider in PROVIDERS.items()
        for model in provider.models
        if "🆓" in model.name or "⚠️" in model.name
    ]

def get_premium_models() -> List[tuple]:
    """Return semua model premium (💎)."""
    return [
        (provider_name, model)
        for provider_name, provider in PROVIDERS.items()
        for model in provider.models
        if "💎" in model.name
    ]
