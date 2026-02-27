"""
Configuration & Provider Registry
All providers, models, and defaults in one place
— Verified against official docs: Feb 27, 2026 —

CHANGELOG:
- [Cerebras]     HAPUS: llama-3.3-70b & qwen-3-32b (DEPRECATED 16 Feb 2026)
                 HAPUS: gpt-oss-20b (tidak ada di daftar resmi)
- [Groq]         TAMBAH: gpt-oss-safeguard-20b, llama3-groq-70b/8b-tool-use
- [OpenRouter]   REVAMP: Bersihkan model tidak aktif, tambah optimus/quasar-alpha,
                         gemini-3-flash-preview, gemini-2.5-pro-exp, solar-pro-3,
                         minimax-m2.1, konfirmasi qwen3-235b-thinking
- [Gemini]       HAPUS: gemini-3.x (belum dikonfirmasi free tier)
                 TAMBAH: gemini-2.0-flash, gemma-3-12b, gemma-3-4b
- [Cloudflare]   TAMBAH: glm-4.7-flash (tools✅), llama-3.2-11b-vision (vision✅)
                 TAMBAH: deepseek-r1-distill-qwen-32b, qwen2.5-coder-32b
- [HuggingFace]  REVISI: Model besar pakai credit, hanya simpan yang benar-benar free
                 TAMBAH: Llama 3.3 70B, Qwen3-235B, QwQ-32B (via router, pakai credit)
- [Cohere]       TAMBAH: command-a-vision, command-a-reasoning
- [SiliconFlow]  TAMBAH: Kimi-K2.5, MiniMax-M2.5, Qwen3-8B
- [Routeway]     OK - tidak ada perubahan
- [Puter]        REVISI: Update nama model ke versi 2026
- [NVIDIA]       TAMBAH: provider baru dengan 20+ model
- [Pollinations] TIDAK DISENTUH

LEGEND:
⭐ = Support Tool Calling (web search, dll)
🔥 = Recommended (fitur lengkap / performa bagus)
👁️ = Vision (bisa lihat gambar)
🧠 = Reasoning mode
🔍 = Search/Grounding built-in
💎 = Paid only
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
    # Docs: https://console.groq.com/docs/models
    # Rate: 30 RPM (70B), 60 RPM (8B) on free tier
    "groq": Provider(
        name="Groq",
        endpoint="https://api.groq.com/openai/v1/chat/completions",
        rate_limit="30 RPM (70B), 60 RPM (8B)",
        models=[
            # ── Compound AI (Web Search built-in) ──────────────────
            Model("compound-beta",      "Groq Compound Beta 🔥🔍⭐",      ["normal", "search"], 131072, tools=True),
            Model("compound-beta-mini", "Groq Compound Beta Mini 🔍⭐",   ["normal", "search"], 131072, tools=True),

            # ── Production ─────────────────────────────────────────
            Model("llama-3.3-70b-versatile", "Llama 3.3 70B ⭐",         ["normal"], 131072, tools=True),
            Model("llama-3.1-8b-instant",    "Llama 3.1 8B ⭐",          ["normal"], 131072, tools=True),

            # ── Fine-tuned Tool Use (Groq) ─────────────────────────
            Model("llama3-groq-70b-8192-tool-use-preview", "Llama 3 Groq 70B Tool Use ⭐", ["normal"], 8192, tools=True),
            Model("llama3-groq-8b-8192-tool-use-preview",  "Llama 3 Groq 8B Tool Use ⭐",  ["normal"], 8192, tools=True),

            # ── GPT-OSS Series ─────────────────────────────────────
            Model("openai/gpt-oss-120b",          "GPT-OSS 120B 🔥⭐🧠",    ["normal", "reasoning"], 131072, tools=True),
            Model("openai/gpt-oss-20b",           "GPT-OSS 20B ⭐",          ["normal"],              131072, tools=True),
            Model("openai/gpt-oss-safeguard-20b", "GPT-OSS Safeguard 20B",   ["normal"],              131072),

            # ── Llama 4 Preview (Vision + Reasoning) ───────────────
            Model("meta-llama/llama-4-maverick-17b-128e-instruct", "Llama 4 Maverick 👁️🧠⭐", ["normal", "reasoning"], 131072, vision=True, tools=True),
            Model("meta-llama/llama-4-scout-17b-16e-instruct",     "Llama 4 Scout 👁️⭐",      ["normal"],              131072, vision=True, tools=True),

            # ── Reasoning ──────────────────────────────────────────
            Model("qwen-qwq-32b",                   "Qwen QWQ 32B 🧠",             ["reasoning"], 131072),
            Model("deepseek-r1-distill-llama-70b",  "DeepSeek R1 Distill 70B 🧠",  ["reasoning"], 131072),

            # ── Preview Chat + Tools ────────────────────────────────
            Model("moonshotai/kimi-k2-instruct-0905", "Kimi K2 ⭐",          ["normal"],              131072, tools=True),
            Model("qwen/qwen-3-32b",                  "Qwen 3 32B 🧠⭐",     ["normal", "reasoning"], 131072, tools=True),

            # ── Audio ──────────────────────────────────────────────
            Model("whisper-large-v3",       "Whisper V3",       ["audio"]),
            Model("whisper-large-v3-turbo", "Whisper V3 Turbo", ["audio"]),
        ]
    ),

    # ==================== OPENROUTER ====================
    # Docs : https://openrouter.ai/models?q=:free
    # Rate : 20 RPM, 200 RPD (free tier)
    # Note : Free model availability berubah frequent — gunakan openrouter/free sebagai fallback
    "openrouter": Provider(
        name="OpenRouter",
        endpoint="https://openrouter.ai/api/v1/chat/completions",
        rate_limit="20 RPM, 200 RPD (free)",
        models=[
            # ── Auto Routers (selalu aktif) ─────────────────────────
            Model("openrouter/free",         "Auto (Free Router) 🔥⭐👁️🧠", ["normal", "reasoning"], 200000,  vision=True, tools=True),
            Model("openrouter/optimus-alpha", "Optimus Alpha 🔥⭐",           ["normal"],              1000000, tools=True),
            Model("openrouter/quasar-alpha",  "Quasar Alpha ⭐",              ["normal"],              1000000, tools=True),

            # ── Google ─────────────────────────────────────────────
            Model("google/gemini-3-flash-preview:free",  "Gemini 3 Flash Preview 🔥👁️🧠⭐", ["normal", "reasoning"], 1000000, vision=True, tools=True),
            Model("google/gemini-2.5-pro-exp-03-25:free","Gemini 2.5 Pro Exp 👁️🧠⭐",       ["normal", "reasoning"], 1000000, vision=True, tools=True),
            Model("google/gemma-3-27b-it:free",          "Gemma 3 27B ⭐",                   ["normal"],               131072,  tools=True),

            # ── Meta Llama 4 ───────────────────────────────────────
            Model("meta-llama/llama-4-maverick:free", "Llama 4 Maverick ⭐👁️🧠", ["normal", "reasoning"], 131072, vision=True, tools=True),
            Model("meta-llama/llama-4-scout:free",    "Llama 4 Scout ⭐👁️🧠",    ["normal", "reasoning"], 131072, vision=True, tools=True),

            # ── Meta Llama 3.3 ─────────────────────────────────────
            Model("meta-llama/llama-3.3-70b-instruct:free", "Llama 3.3 70B ⭐", ["normal"], 131072, tools=True),

            # ── DeepSeek ───────────────────────────────────────────
            Model("deepseek/deepseek-chat-v3-0324:free", "DeepSeek Chat V3 ⭐", ["normal"],    64000, tools=True),
            Model("deepseek/deepseek-v3-base:free",      "DeepSeek V3 Base",    ["normal"],    64000),
            Model("deepseek/deepseek-r1-zero:free",      "DeepSeek R1 Zero 🧠", ["reasoning"], 64000),
            Model("deepseek/deepseek-r1:free",           "DeepSeek R1 🧠",      ["reasoning"], 64000),

            # ── Mistral ────────────────────────────────────────────
            Model("mistralai/mistral-small-3.1-24b-instruct:free", "Mistral Small 3.1 ⭐", ["normal"], 32768, tools=True),

            # ── Qwen ───────────────────────────────────────────────
            Model("qwen/qwen3-coder:free",                    "Qwen3 Coder 480B 🔥⭐🧠", ["normal", "reasoning"], 262144, tools=True),
            Model("qwen/qwen3-235b-a22b-thinking-2507:free",  "Qwen3 235B Thinking 🧠⭐", ["reasoning"],          262144, tools=True),
            Model("qwen/qwen2.5-vl-3b-instruct:free",         "Qwen 2.5 VL 3B 👁️",       ["normal"],             32768,  vision=True),

            # ── ZhipuAI GLM ────────────────────────────────────────
            Model("zhipuai/glm-4.5-air:free", "GLM 4.5 Air ⭐🧠", ["normal", "reasoning"], 128000, tools=True),

            # ── NVIDIA ─────────────────────────────────────────────
            Model("nvidia/llama-3.1-nemotron-nano-8b-v1:free", "Nemotron Nano 8B ⭐",    ["normal"], 131072, tools=True),
            Model("nvidia/nemotron-3-nano-30b-a3b:free",       "Nemotron 3 Nano 30B ⭐", ["normal"], 256000, tools=True),

            # ── StepFun ────────────────────────────────────────────
            Model("stepfun/step-3.5-flash:free", "Step 3.5 Flash ⭐🧠", ["reasoning"], 256000, tools=True),

            # ── Upstage ────────────────────────────────────────────
            Model("upstage/solar-pro-3:free", "Solar Pro 3 (102B MoE)", ["normal"], 131072),

            # ── MiniMax ────────────────────────────────────────────
            Model("minimax/minimax-m2.1:free", "MiniMax M2.1 ⭐🧠", ["normal"], 1000000, tools=True),

            # ── Arcee ──────────────────────────────────────────────
            Model("arcee-ai/trinity-large-preview:free", "Trinity Large Preview ⭐", ["normal"], 128000, tools=True),

            # ── Moonshot ───────────────────────────────────────────
            Model("moonshotai/kimi-vl-a3b-thinking:free", "Kimi VL Thinking 👁️🧠", ["reasoning"], 128000, vision=True),

            # ── NousResearch ───────────────────────────────────────
            Model("nousresearch/deephermes-3-llama-3-8b-preview:free", "DeepHermes 3 8B", ["normal"], 131072),
        ]
    ),

    # ==================== GEMINI ====================
    # Docs: https://ai.google.dev/gemini-api/docs/models
    # Rate: 15 RPM, 1500 RPD (free tier via AI Studio)
    "gemini": Provider(
        name="Google Gemini",
        endpoint="https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        auth_header="x-goog-api-key",
        auth_prefix="",
        rate_limit="15 RPM, 1500 RPD (free tier)",
        models=[
            # ── Gemini 2.5 (Stable, Free Tier) ────────────────────
            Model("gemini-2.5-pro",       "Gemini 2.5 Pro 🔥🧠⭐",   ["normal", "reasoning"], 1048576, tools=True),
            Model("gemini-2.5-flash",     "Gemini 2.5 Flash 🧠⭐",   ["normal", "reasoning"], 1048576, tools=True),
            Model("gemini-2.5-flash-lite","Gemini 2.5 Flash Lite ⭐", ["normal"],              1048576, tools=True),

            # ── Gemini 2.0 ─────────────────────────────────────────
            Model("gemini-2.0-flash",      "Gemini 2.0 Flash 👁️⭐",      ["normal"], 1048576, vision=True, tools=True),
            Model("gemini-2.0-flash-lite", "Gemini 2.0 Flash Lite",       ["normal"], 1048576),

            # ── Gemma (Open Source via AI Studio) ─────────────────
            Model("gemma-3-27b-it", "Gemma 3 27B ⭐", ["normal"], 131072, tools=True),
            Model("gemma-3-12b-it", "Gemma 3 12B",    ["normal"], 131072),
            Model("gemma-3-4b-it",  "Gemma 3 4B",     ["normal"], 131072),
        ]
    ),

    # ==================== CEREBRAS ====================
    # Docs: https://inference-docs.cerebras.ai/introduction
    # Rate: 30 RPM, 1M tokens/day (free tier)
    # Note: llama-3.3-70b & qwen-3-32b DEPRECATED 16 Feb 2026
    "cerebras": Provider(
        name="Cerebras",
        endpoint="https://api.cerebras.ai/v1/chat/completions",
        rate_limit="30 RPM, 1M tokens/day (free tier)",
        models=[
            # ── Aktif (Confirmed Feb 27, 2026) ────────────────────
            Model("zai-glm-4.7",                     "Z.ai GLM 4.7 🔥⭐🧠",      ["normal", "reasoning"], 128000, tools=True),
            Model("gpt-oss-120b",                    "GPT-OSS 120B 🔥⭐🧠",      ["normal", "reasoning"], 131072, tools=True),
            Model("llama3.1-8b",                     "Llama 3.1 8B ⭐",           ["normal"],              128000, tools=True),
            Model("qwen-3-235b-a22b-instruct-2507",  "Qwen 3 235B Instruct ⭐🧠", ["normal", "reasoning"], 262144, tools=True),
        ]
    ),

    # ==================== SAMBANOVA ====================
    # Docs: https://community.sambanova.ai/t/supported-models/193
    # Rate: Free tier available
    "sambanova": Provider(
        name="SambaNova",
        endpoint="https://api.sambanova.ai/v1/chat/completions",
        rate_limit="Free tier available",
        models=[
            # ── Chat + Tools ───────────────────────────────────────
            Model("Meta-Llama-3.1-8B-Instruct",  "Llama 3.1 8B ⭐",  ["normal"], 8192,   tools=True),
            Model("Meta-Llama-3.3-70B-Instruct", "Llama 3.3 70B ⭐", ["normal"], 131072, tools=True),

            # ── Vision + Tools ─────────────────────────────────────
            Model("Llama-4-Scout-17B-16E-Instruct",    "Llama 4 Scout ⭐👁️",    ["normal"], 131072, vision=True, tools=True),
            Model("Llama-4-Maverick-17B-128E-Instruct","Llama 4 Maverick ⭐👁️", ["normal"], 131072, vision=True, tools=True),

            # ── Reasoning ──────────────────────────────────────────
            Model("DeepSeek-R1",                  "DeepSeek R1 🧠",             ["reasoning"],           16384),
            Model("DeepSeek-R1-Distill-Llama-70B","DeepSeek R1 Distill 70B 🧠", ["reasoning"],          131072),
            Model("DeepSeek-V3-0324",             "DeepSeek V3 0324 ⭐",        ["normal"],              8192,   tools=True),

            # ── Reasoning + Tools ──────────────────────────────────
            Model("Qwen3-32B",    "Qwen 3 32B ⭐🧠",       ["normal", "reasoning"], 32768,  tools=True),
            Model("QwQ-32B",      "QwQ 32B 🧠",            ["reasoning"],           32768),
            Model("gpt-oss-120b", "GPT-OSS 120B 🔥⭐🧠",   ["normal", "reasoning"], 131072, tools=True),
        ]
    ),

    # ==================== NVIDIA NIM ====================
    # Docs: https://build.nvidia.com/explore/discover
    # Rate: Free tier (unlimited prototyping via hosted DGX Cloud)
    # Key : Daftar gratis di https://build.nvidia.com
    "nvidia": Provider(
        name="NVIDIA NIM",
        endpoint="https://integrate.api.nvidia.com/v1/chat/completions",
        rate_limit="Free tier (unlimited prototyping)",
        models=[
            # ── GPT-OSS (OpenAI Open Weight) ───────────────────────
            Model("openai/gpt-oss-120b", "GPT-OSS 120B 🔥⭐🧠", ["normal", "reasoning"], 131072, tools=True),
            Model("openai/gpt-oss-20b",  "GPT-OSS 20B ⭐",       ["normal"],              131072, tools=True),

            # ── Nemotron (NVIDIA's Own) ────────────────────────────
            Model("nvidia/llama-3.3-nemotron-super-49b-v1",  "Nemotron Super 49B 🔥⭐🧠",  ["normal", "reasoning"], 131072, tools=True),
            Model("nvidia/llama-3.1-nemotron-nano-8b-v1",    "Nemotron Nano 8B ⭐🧠",       ["normal", "reasoning"], 131072, tools=True),
            Model("nvidia/llama-3.3-nemotron-ultra-253b-v1", "Nemotron Ultra 253B 🔥⭐🧠",  ["normal", "reasoning"], 131072, tools=True),
            Model("nvidia/nemotron-nano-2-vl-12b",           "Nemotron Nano 2 VL 12B 👁️🧠",["normal", "reasoning"], 128000, vision=True),

            # ── Qwen 3 ─────────────────────────────────────────────
            Model("qwen/qwen3-235b-a22b",  "Qwen 3 235B A22B 🔥⭐🧠", ["normal", "reasoning"], 131072, tools=True),
            Model("qwen/qwen3-32b",        "Qwen 3 32B ⭐🧠",          ["normal", "reasoning"], 131072, tools=True),
            Model("qwen/qwq-32b",          "QwQ 32B 🧠⭐",             ["reasoning"],           40960,  tools=True),
            Model("qwen/qwen3-coder",      "Qwen 3 Coder 🔥⭐🧠",      ["normal", "reasoning"], 262144, tools=True),

            # ── DeepSeek ───────────────────────────────────────────
            Model("deepseek-ai/deepseek-r1-0528",  "DeepSeek R1 0528 🧠⭐", ["reasoning"], 131072, tools=True),
            Model("deepseek-ai/deepseek-v3-0324",  "DeepSeek V3 0324 ⭐",   ["normal"],    131072, tools=True),

            # ── Meta Llama 4 ───────────────────────────────────────
            Model("meta/llama-4-scout-17b-16e-instruct",    "Llama 4 Scout 👁️⭐",    ["normal"],              131072, vision=True, tools=True),
            Model("meta/llama-4-maverick-17b-128e-instruct","Llama 4 Maverick 👁️⭐🧠",["normal", "reasoning"], 131072, vision=True, tools=True),

            # ── Meta Llama 3.x ─────────────────────────────────────
            Model("meta/llama-3.3-70b-instruct", "Llama 3.3 70B ⭐", ["normal"], 131072, tools=True),
            Model("meta/llama-3.1-70b-instruct", "Llama 3.1 70B ⭐", ["normal"], 131072, tools=True),
            Model("meta/llama-3.1-8b-instruct",  "Llama 3.1 8B ⭐",  ["normal"], 131072, tools=True),

            # ── Mistral ────────────────────────────────────────────
            Model("mistralai/mistral-small-3.2-24b-instruct", "Mistral Small 3.2 24B ⭐", ["normal"], 131072, tools=True),
            Model("mistralai/mixtral-8x7b-instruct-v0.1",     "Mixtral 8x7B ⭐",          ["normal"], 32768,  tools=True),

            # ── Moonshot ───────────────────────────────────────────
            Model("moonshotai/kimi-k2.5",          "Kimi K2.5 👁️⭐🧠", ["normal", "reasoning"], 131072, vision=True, tools=True),
            Model("moonshotai/kimi-k2-instruct",   "Kimi K2 ⭐",        ["normal"],              131072, tools=True),

            # ── MiniMax ────────────────────────────────────────────
            Model("minimax/minimax-01", "MiniMax M2 🔥⭐", ["normal"], 1048576, tools=True),

            # ── Google Gemma ───────────────────────────────────────
            Model("google/gemma-3-27b-it", "Gemma 3 27B", ["normal"], 131072),
            Model("google/gemma-3-12b-it", "Gemma 3 12B", ["normal"], 131072),
        ]
    ),

    # ==================== POLLINATIONS ====================
    # ⚠️ TIDAK DISENTUH sesuai permintaan
    "pollinations": Provider(
        name="Pollinations",
        endpoint="https://gen.pollinations.ai/v1/chat/completions",
        auth_header="Authorization",
        auth_prefix="Bearer",
        rate_limit="1/15s (anon), unlimited (sk_)",
        models=[
            # Fast / Cheap
            Model("qwen-safety", "Qwen3Guard 8B",            ["normal"]),
            Model("nova-fast",   "Amazon Nova Micro",         ["normal"]),
            Model("openai-fast", "OpenAI GPT-5 Nano 👁️",    ["normal"], vision=True),
            Model("gemini-fast", "Gemini 2.5 Flash Lite 👁️", ["normal"], vision=True),
            Model("qwen-coder",  "Qwen3 Coder 30B",           ["normal"]),
            Model("mistral",     "Mistral Small 3.2 24B",     ["normal"]),

            # Mid Tier
            Model("openai",   "OpenAI GPT-5 Mini 👁️", ["normal"], vision=True),
            Model("deepseek", "DeepSeek V3.2",         ["normal"]),
            Model("minimax",  "MiniMax M2.1",           ["normal"]),
            Model("kimi",     "Kimi K2.5 👁️",          ["normal"], vision=True),
            Model("glm",      "Z.ai GLM-5",             ["normal"]),

            # Search Built-in
            Model("perplexity-fast", "Perplexity Sonar 🔍",              ["search"]),
            Model("gemini-search",   "Gemini 2.5 Flash Search 🔥🔍👁️", ["search"], vision=True, tools=True),

            # Premium
            Model("openai-large",        "OpenAI GPT-5.2 👁️",           ["normal"],            vision=True),
            Model("perplexity-reasoning","Perplexity Reasoning 🔍🧠",    ["reasoning", "search"]),
            Model("openai-audio",        "GPT-4o Mini Audio 👁️",         ["normal"],            vision=True),
            Model("chickytutor",         "ChickyTutor AI",                ["normal"]),
            Model("midijourney",         "MIDIjourney",                   ["normal"]),

            # PAID ONLY (💎)
            Model("grok",          "xAI Grok 4 Fast 💎",          ["normal"]),
            Model("gemini",        "Google Gemini 3 Flash 💎👁️",  ["normal"],              vision=True),
            Model("claude-fast",   "Claude Haiku 4.5 💎👁️",       ["normal"],              vision=True),
            Model("gemini-legacy", "Gemini 2.5 Pro 💎👁️🧠",       ["normal", "reasoning"], vision=True),
            Model("claude",        "Claude Sonnet 4.6 💎👁️",      ["normal"],              vision=True),
            Model("gemini-large",  "Gemini 3 Pro 💎👁️🧠",         ["normal", "reasoning"], vision=True),
            Model("claude-large",  "Claude Opus 4.6 💎👁️",        ["normal"],              vision=True),
            Model("claude-legacy", "Claude Opus 4.5 💎👁️",        ["normal"],              vision=True),

            # Alpha / Community
            Model("nomnom", "NomNom 🔍🧠",            ["reasoning", "search"]),
            Model("polly",  "Polly 🔥🔍👁️🧠",        ["normal", "reasoning", "search"], vision=True),
        ]
    ),

    # ==================== CLOUDFLARE ====================
    # Docs: https://developers.cloudflare.com/workers-ai/models/
    # Rate: 10K neurons/day (free tier)
    "cloudflare": Provider(
        name="Cloudflare",
        endpoint="https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}",
        rate_limit="10K neurons/day",
        models=[
            # ── Vision ─────────────────────────────────────────────
            Model("@cf/meta/llama-3.2-11b-vision-instruct",     "Llama 3.2 11B Vision 👁️",  ["normal"], 131072, vision=True),

            # ── Chat + Tools ───────────────────────────────────────
            Model("@cf/meta/llama-4-scout-17b-16e-instruct",    "Llama 4 Scout 🧠⭐",        ["normal", "reasoning"], 131072, tools=True),
            Model("@cf/meta/llama-3.3-70b-instruct-fp8-fast",   "Llama 3.3 70B ⭐",          ["normal"],              131072, tools=True),
            Model("@cf/meta/llama-3.1-8b-instruct",             "Llama 3.1 8B ⭐",           ["normal"],              131072, tools=True),
            Model("@cf/mistralai/mistral-small-3.1-24b-instruct","Mistral Small 3.1 ⭐",      ["normal"],              32768,  tools=True),
            Model("@cf/qwen/qwen2.5-coder-32b-instruct",        "Qwen 2.5 Coder 32B ⭐",     ["normal"],              32768,  tools=True),
            Model("@cf/zai-org/glm-4.7-flash",                  "GLM 4.7 Flash ⭐",          ["normal"],              131072, tools=True),

            # ── Reasoning ──────────────────────────────────────────
            Model("@cf/deepseek-ai/deepseek-r1-distill-qwen-32b","DeepSeek R1 Distill 32B 🧠",["reasoning"], 32768),

            # ── Chat ───────────────────────────────────────────────
            Model("@cf/google/gemma-3-12b-it",                  "Gemma 3 12B",               ["normal"], 131072),
        ]
    ),

    # ==================== HUGGINGFACE ====================
    # Docs: https://huggingface.co/docs/api-inference/index
    # Rate: ~50 calls/day (serverless free)
    # ⚠️ PENTING: Model besar (70B+) memerlukan HF credit via Inference Providers
    #             Model kecil (7B-) masih bisa via serverless gratis
    "huggingface": Provider(
        name="HuggingFace",
        endpoint="https://router.huggingface.co/v1/chat/completions",
        rate_limit="~50 calls/day (free serverless), credit-based (large models)",
        models=[
            # ── Gratis via Serverless (model kecil) ───────────────
            Model("mistralai/Mistral-7B-Instruct-v0.3", "Mistral 7B",  ["normal"], 32768),
            Model("HuggingFaceH4/zephyr-7b-beta",       "Zephyr 7B",   ["normal"], 32768),

            # ── Via Inference Providers (pakai HF credit) ─────────
            Model("meta-llama/Llama-3.3-70B-Instruct",      "Llama 3.3 70B ⭐",   ["normal"],              131072, tools=True),
            Model("meta-llama/Meta-Llama-3.1-8B-Instruct",  "Llama 3.1 8B",       ["normal"],              131072),
            Model("Qwen/Qwen3-235B-A22B",                   "Qwen 3 235B 🧠⭐",   ["normal", "reasoning"], 131072, tools=True),
            Model("Qwen/QwQ-32B",                           "QwQ 32B 🧠",         ["reasoning"],           32768),
            Model("deepseek-ai/DeepSeek-R1",                "DeepSeek R1 🧠",     ["reasoning"],           131072),
            Model("deepseek-ai/DeepSeek-R1-0528",           "DeepSeek R1 0528 🧠",["reasoning"],           131072),
            Model("deepseek-ai/DeepSeek-R1-Distill-Qwen-7B","DeepSeek R1 Distill 7B 🧠", ["reasoning"],   32768),
            Model("deepseek-ai/DeepSeek-R1-Distill-Llama-70B","DeepSeek R1 Distill 70B 🧠",["reasoning"], 131072),
        ]
    ),

    # ==================== COHERE ====================
    # Docs: https://docs.cohere.com/v2/docs/models
    # Rate: 1000 calls/month (trial key, gratis)
    "cohere": Provider(
        name="Cohere",
        endpoint="https://api.cohere.ai/v2/chat",
        rate_limit="1000 calls/month (trial)",
        models=[
            # ── Flagship ───────────────────────────────────────────
            Model("command-a-03-2025",           "Command A ⭐",                ["normal"],              256000, tools=True),
            Model("command-a-vision-03-2025",    "Command A Vision 👁️⭐",      ["normal"],              256000, vision=True, tools=True),
            Model("command-a-reasoning-03-2025", "Command A Reasoning 🧠⭐",   ["normal", "reasoning"], 256000, tools=True),

            # ── Standard ───────────────────────────────────────────
            Model("command-r-plus-08-2024", "Command R+ 🔍⭐", ["normal", "search"], 128000, tools=True),
            Model("command-r-08-2024",      "Command R ⭐",    ["normal"],            128000, tools=True),
            Model("command-r7b-12-2024",    "Command R 7B ⭐", ["normal"],            128000, tools=True),
        ]
    ),

    # ==================== SILICONFLOW ====================
    # Docs: https://docs.siliconflow.cn/en/api-reference
    # Rate: 100 RPD (free models), varies (paid)
    "siliconflow": Provider(
        name="SiliconFlow",
        endpoint="https://api.siliconflow.com/v1/chat/completions",
        rate_limit="100 RPD (free models)",
        models=[
            # ── FREE Models ────────────────────────────────────────
            Model("Qwen/Qwen2.5-7B-Instruct",              "Qwen 2.5 7B",            ["normal"],              32768),
            Model("Qwen/Qwen2.5-Coder-7B-Instruct",        "Qwen 2.5 Coder 7B",      ["normal"],              32768),
            Model("Pro/Qwen/Qwen3-8B",                     "Qwen 3 8B 🧠⭐",         ["normal", "reasoning"], 40960,  tools=True),
            Model("THUDM/GLM-4-9B-0414",                   "GLM 4 9B 0414",           ["normal"],              128000),
            Model("deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", "DeepSeek R1 Distill 7B 🧠",  ["reasoning"],     32768),
            Model("deepseek-ai/DeepSeek-R1-Distill-Qwen-14B","DeepSeek R1 Distill 14B 🧠", ["reasoning"],     32768),
            Model("deepseek-ai/DeepSeek-R1-Distill-Qwen-32B","DeepSeek R1 Distill 32B 🧠", ["reasoning"],     32768),
            Model("Qwen/QwQ-32B",                          "QwQ 32B 🧠",             ["reasoning"],           32768),

            # ── PAID Models ────────────────────────────────────────
            Model("deepseek-ai/DeepSeek-R1-0528",          "DeepSeek R1 0528 🧠",    ["reasoning"],           164000),
            Model("deepseek-ai/DeepSeek-R1",               "DeepSeek R1 🧠",         ["reasoning"],           164000),
            Model("deepseek-ai/DeepSeek-V3-0324",          "DeepSeek V3 0324 ⭐",    ["normal"],              164000, tools=True),
            Model("Qwen/Qwen2.5-Coder-32B-Instruct",       "Qwen 2.5 Coder 32B",     ["normal"],              32768),
            Model("Qwen/Qwen3-32B",                        "Qwen 3 32B 🧠⭐",        ["normal", "reasoning"], 32768,  tools=True),
            Model("moonshotai/Kimi-K2.5",                  "Kimi K2.5 👁️⭐🧠",      ["normal", "reasoning"], 262144, vision=True, tools=True),
            Model("MiniMax/MiniMax-M2.5",                  "MiniMax M2.5 ⭐",        ["normal"],              197000, tools=True),
        ]
    ),

    # ==================== ROUTEWAY ====================
    # Docs: https://routeway.ai/docs
    # Rate: 20 RPM, 200 RPD (free models)
    # Note: $1 free credit saat daftar, 70+ model via unified API
    "routeway": Provider(
        name="Routeway",
        endpoint="https://api.routeway.ai/v1/chat/completions",
        rate_limit="20 RPM, 200 RPD (free models)",
        models=[
            Model("glm-4.6:free",                "GLM 4.6 🔥⭐🧠",   ["normal", "reasoning"], 200000, tools=True),
            Model("glm-4.5-air:free",            "GLM 4.5 Air",       ["normal"],              131000),
            Model("deepseek-r1:free",            "DeepSeek R1 🧠",   ["reasoning"],           164000),
            Model("minimax-m2:free",             "MiniMax M2",        ["normal"],              197000),
            Model("kimi-k2:free",                "Kimi K2 ⭐",        ["normal"],              262000, tools=True),
            Model("deepseek-v3.1:free",          "DeepSeek V3.1 ⭐", ["normal"],              131000, tools=True),
            Model("llama-3.3-70b-instruct:free", "Llama 3.3 70B ⭐", ["normal"],              131000, tools=True),
            Model("mistral-small-3:free",        "Mistral Small 3 ⭐",["normal"],              32768,  tools=True),
        ]
    ),

    # ==================== MLVOCA ====================
    # Note: No API key required, unlimited, model kecil saja
    "mlvoca": Provider(
        name="MLVOCA",
        endpoint="https://mlvoca.com/api/generate",
        auth_header="",
        auth_prefix="",
        rate_limit="unlimited",
        models=[
            Model("tinyllama",       "TinyLlama",          ["normal"]),
            Model("deepseek-r1:1.5b","DeepSeek R1 1.5B 🧠",["reasoning"]),
        ]
    ),

    # ==================== PUTER ====================
    # Docs: https://docs.puter.com/AI/chat/
    # Note: User-pays model — developer gratis, user pakai akun Puter sendiri
    #       500+ model tersedia, tidak perlu API key developer
    "puter": Provider(
        name="Puter",
        endpoint="https://api.puter.com/drivers/call",
        rate_limit="Free Tier (Puter.com) — User-Pays",
        models=[
            # ── OpenAI ─────────────────────────────────────────────
            Model("gpt-5-nano",  "GPT-5 Nano 👁️⭐",  ["normal"], 128000, vision=True, tools=True),
            Model("gpt-5-mini",  "GPT-5 Mini 👁️⭐",  ["normal"], 128000, vision=True, tools=True),
            Model("gpt-4.1-nano","GPT-4.1 Nano ⭐",   ["normal"], 128000, tools=True),

            # ── Anthropic ──────────────────────────────────────────
            Model("claude-sonnet-4-5","Claude Sonnet 4.5 🔥🧠", ["normal", "reasoning"], 200000),
            Model("claude-3-5-sonnet","Claude 3.5 Sonnet 🧠",   ["normal", "reasoning"], 200000),

            # ── Google ─────────────────────────────────────────────
            Model("google/gemini-2.5-flash",    "Gemini 2.5 Flash 🧠⭐",    ["normal", "reasoning"], 1048576, tools=True),
            Model("google/gemini-2.5-pro",      "Gemini 2.5 Pro 🔥🧠⭐",   ["normal", "reasoning"], 1048576, tools=True),
            Model("gemini-2.5-flash-lite",      "Gemini 2.5 Flash Lite ⭐", ["normal"],              1048576, tools=True),

            # ── DeepSeek ───────────────────────────────────────────
            Model("deepseek/deepseek-r1",   "DeepSeek R1 🧠",   ["reasoning"], 128000),
            Model("deepseek/deepseek-chat", "DeepSeek V3 ⭐",   ["normal"],    128000, tools=True),

            # ── xAI Grok ───────────────────────────────────────────
            Model("x-ai/grok-4-1-fast", "Grok 4.1 Fast 🔥⭐", ["normal"], 131072, tools=True),
            Model("x-ai/grok-4-1-mini", "Grok 4.1 Mini ⭐",   ["normal"], 131072, tools=True),

            # ── Meta ───────────────────────────────────────────────
            Model("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B ⭐", ["normal"], 131072, tools=True),

            # ── Perplexity ─────────────────────────────────────────
            Model("perplexity/sonar",     "Perplexity Sonar 🔍",      ["search"], 128000),
            Model("perplexity/sonar-pro", "Perplexity Sonar Pro 🔥🔍",["search"], 200000),
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
# FALLBACK CHAINS
# ============================================================

FALLBACK_CHAINS = {
    "normal": [
        ("groq",        "llama-3.3-70b-versatile"),
        ("groq",        "llama-3.1-8b-instant"),
        ("cerebras",    "llama3.1-8b"),
        ("nvidia",      "meta/llama-3.3-70b-instruct"),
        ("sambanova",   "Meta-Llama-3.3-70B-Instruct"),
        ("openrouter",  "openrouter/free"),
        ("openrouter",  "meta-llama/llama-3.3-70b-instruct:free"),
        ("openrouter",  "deepseek/deepseek-chat-v3-0324:free"),
        ("cloudflare",  "@cf/meta/llama-3.3-70b-instruct-fp8-fast"),
        ("cloudflare",  "@cf/meta/llama-3.1-8b-instruct"),
        ("pollinations","openai"),
        ("puter",       "gpt-5-mini"),
    ],
    "reasoning": [
        ("groq",        "deepseek-r1-distill-llama-70b"),
        ("groq",        "qwen-qwq-32b"),
        ("groq",        "openai/gpt-oss-120b"),
        ("cerebras",    "gpt-oss-120b"),
        ("cerebras",    "zai-glm-4.7"),
        ("nvidia",      "nvidia/llama-3.3-nemotron-ultra-253b-v1"),
        ("nvidia",      "deepseek-ai/deepseek-r1-0528"),
        ("sambanova",   "DeepSeek-R1"),
        ("openrouter",  "openrouter/free"),
        ("openrouter",  "deepseek/deepseek-r1:free"),
        ("openrouter",  "stepfun/step-3.5-flash:free"),
        ("openrouter",  "qwen/qwen3-coder:free"),
        ("cloudflare",  "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b"),
        ("pollinations","perplexity-reasoning"),
        ("routeway",    "deepseek-r1:free"),
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
        ("sambanova",   "Llama-4-Maverick-17B-128E-Instruct"),
        ("nvidia",      "meta/llama-4-maverick-17b-128e-instruct"),
        ("openrouter",  "meta-llama/llama-4-maverick:free"),
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
