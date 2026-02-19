"""
Configuration & Provider Registry
All providers, models, and defaults in one place
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
    "groq": os.getenv("GROQ_API_KEY"),
    "openrouter": os.getenv("OPENROUTER_API_KEY"),
    "pollinations": os.getenv("POLLINATIONS_API_KEY"),  # Optional
    "gemini": os.getenv("GEMINI_API_KEY"),
    "cerebras": os.getenv("CEREBRAS_API_KEY"),
    "cloudflare": os.getenv("CLOUDFLARE_API_TOKEN"),
    "cloudflare_account": os.getenv("CLOUDFLARE_ACCOUNT_ID"),
    "huggingface": os.getenv("HUGGINGFACE_TOKEN"),
    "cohere": os.getenv("COHERE_API_KEY"),
    "siliconflow": os.getenv("SILICONFLOW_API_KEY"),
    "routeway": os.getenv("ROUTEWAY_API_KEY"),
    "tavily": os.getenv("TAVILY_API_KEY"),
    "brave": os.getenv("BRAVE_API_KEY"),
    "serper": os.getenv("SERPER_API_KEY"),
    
    # Puter.com - Free 200+ AI Models (create account at puter.com)
    "puter_api_key": os.getenv("PUTER_API_KEY"),}

# ============================================================
# DEFAULTS
# ============================================================

DEFAULTS = {
    "provider": os.getenv("DEFAULT_PROVIDER", "groq"),
    "model": os.getenv("DEFAULT_MODEL", "llama-3.3-70b-versatile"),
    "mode": "normal",           # normal | reasoning | search
    "auto_chat": False,         # False = mention only (anti-spam)
    "auto_detect": False,       # False = manual mode selection
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

# ------------------------------------------------------------
# ALL PROVIDERS (Verified Feb 2026)
# ------------------------------------------------------------

PROVIDERS: Dict[str, Provider] = {
    
    # ==================== GROQ ====================
    "groq": Provider(
        name="Groq",
        endpoint="https://api.groq.com/openai/v1/chat/completions",
        rate_limit="100 RPM",
        models=[
            # Production
            Model("groq/compound", "Groq Compound (Web Search)", ["normal", "search"], 131072),
                Model("groq/compound-mini", "Groq Compound Mini (Fast)", ["normal", "search"], 131072),
                Model("compound-beta", "Groq Compound Beta", ["normal", "search"], 131072),
                Model("compound-beta-mini", "Groq Compound Beta Mini", ["normal", "search"], 131072),
                Model("llama-3.3-70b-versatile", "Llama 3.3 70B", ["normal"], 131072),
            Model("llama-3.1-8b-instant", "Llama 3.1 8B", ["normal"], 131072),
            Model("openai/gpt-oss-120b", "GPT-OSS 120B", ["normal", "reasoning"], 131072, tools=True),
            Model("openai/gpt-oss-20b", "GPT-OSS 20B", ["normal"], 131072),
            # Preview
            Model("meta-llama/llama-4-maverick-17b-128e-instruct", "Llama 4 Maverick", ["reasoning"], 131072, vision=True),
            Model("meta-llama/llama-4-scout-17b-16e-instruct", "Llama 4 Scout", ["reasoning"], 131072, vision=True),
            Model("qwen/qwen3-32b", "Qwen QWQ 32B", ["reasoning"], 32768),
            Model("deepseek-r1-distill-llama-70b", "DeepSeek R1 Distill", ["reasoning"], 32768),
            Model("moonshotai/kimi-k2-instruct-0905", "Kimi K2", ["normal"], 131072),
            Model("qwen/qwen3-32b", "Qwen 3 32B", ["normal"], 32768),
            # Audio
            Model("whisper-large-v3", "Whisper V3", ["audio"]),
            Model("whisper-large-v3-turbo", "Whisper V3 Turbo", ["audio"]),
        ]
    ),
    
    # ==================== OPENROUTER ====================
    "openrouter": Provider(
        name="OpenRouter",
        endpoint="https://openrouter.ai/api/v1/chat/completions",
        rate_limit="20 RPM, 200 RPD",
        models=[
            # Router
            Model("openrouter/free", "Auto (Free)", ["normal"]),
            # Reasoning
            Model("deepseek/deepseek-r1:free", "DeepSeek R1", ["reasoning"], 164000),
            Model("deepseek/deepseek-r1-0528:free", "DeepSeek R1 0528", ["reasoning"], 164000),
            Model("deepseek/deepseek-r1-zero:free", "DeepSeek R1 Zero", ["reasoning"]),
            Model("qwen/qwen3-coder:free", "Qwen3 Coder", ["reasoning", "normal"], 262144, tools=True),
            Model("stepfun/step-3.5-flash:free", "Step 3.5 Flash", ["reasoning"], 262144),
            Model("google/gemini-2.5-pro-exp-03-25:free", "Gemini 2.5 Pro Exp", ["reasoning"]),
            Model("moonshotai/kimi-vl-a3b-thinking:free", "Kimi VL Thinking", ["reasoning"], vision=True),
            # Normal
            Model("meta-llama/llama-4-maverick:free", "Llama 4 Maverick", ["normal", "reasoning"]),
            Model("meta-llama/llama-4-scout:free", "Llama 4 Scout", ["normal", "reasoning"]),
            Model("deepseek/deepseek-v3-base:free", "DeepSeek V3", ["normal"]),
            Model("deepseek/deepseek-chat-v3-0324:free", "DeepSeek Chat V3", ["normal"]),
            Model("mistralai/mistral-small-3.1-24b-instruct:free", "Mistral Small 3.1", ["normal"]),
            Model("nvidia/llama-3.1-nemotron-nano-8b-v1:free", "Nemotron Nano 8B", ["normal"]),
            Model("qwen/qwen2.5-vl-3b-instruct:free", "Qwen 2.5 VL 3B", ["normal"], vision=True),
            # New Feb 2026
            Model("qwen/qwen3-next-80b-a3b-instruct:free", "Qwen3 Next 80B", ["normal"], 262144, tools=True),
            Model("nvidia/nemotron-3-nano-30b-a3b:free", "Nemotron 3 Nano 30B", ["normal"], 262144, tools=True),
            Model("arcee-ai/trinity-large-preview:free", "Trinity Large", ["normal"], 524288),
            Model("zhipuai/glm-4.5-air:free", "GLM 4.5 Air", ["normal", "reasoning"]),
        ]
    ),
    
    # ==================== POLLINATIONS ====================
    "pollinations": Provider(
        name="Pollinations",
        endpoint="https://gen.pollinations.ai/v1/chat/completions",
        auth_header="Authorization",
        auth_prefix="Bearer",
        rate_limit="1/15s (anon), unlimited (sk_)",
        models=[
            # Text
            Model("openai", "OpenAI (GPT-5)", ["normal"]),
            Model("openai-fast", "OpenAI Fast", ["normal"]),
            Model("openai-large", "OpenAI Large", ["normal"]),
            Model("gemini", "Gemini", ["normal"]),
            Model("gemini-fast", "Gemini Fast", ["normal"]),
            Model("gemini-large", "Gemini Large", ["normal"]),
            Model("gemini-search", "Gemini Search", ["search"], tools=True),
            Model("deepseek", "DeepSeek V3.2", ["normal"]),
            Model("claude", "Claude", ["normal"]),
            Model("claude-fast", "Claude Fast", ["normal"]),
            Model("claude-large", "Claude Large", ["normal"]),
            Model("mistral", "Mistral", ["normal"]),
            Model("grok", "Grok", ["normal"]),
            Model("qwen-coder", "Qwen3 Coder", ["normal"]),
            Model("kimi", "Kimi K2.5", ["normal"]),
            Model("glm", "GLM", ["normal"]),
            Model("minimax", "MiniMax", ["normal"]),
            # Reasoning + Search
            Model("perplexity-fast", "Perplexity Fast", ["search"]),
            Model("perplexity-reasoning", "Perplexity Reasoning", ["reasoning", "search"]),
        ]
    ),
    
    # ==================== GEMINI ====================
    "gemini": Provider(
        name="Google Gemini",
        endpoint="https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        auth_header="x-goog-api-key",
        auth_prefix="",
        rate_limit="5-15 RPM, 100-1000 RPD",
        models=[
            Model("gemini-2.5-pro", "Gemini 2.5 Pro", ["normal", "reasoning"]),
            Model("gemini-2.5-flash", "Gemini 2.5 Flash", ["normal", "reasoning"]),
            Model("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite", ["normal"]),
            Model("gemini-3-flash-preview", "Gemini 3 Flash", ["normal", "reasoning"]),
            Model("gemma-3-27b-it", "Gemma 3 27B", ["normal"]),
            Model("gemma-2-9b-it", "Gemma 2 9B", ["normal"]),
        ]
    ),
    
    # ==================== CEREBRAS ====================
    "cerebras": Provider(
        name="Cerebras",
        endpoint="https://api.cerebras.ai/v1/chat/completions",
        rate_limit="1M tokens/day",
        models=[
            Model("llama3.1-8b", "Llama 3.1 8B", ["normal"]),
            Model("gpt-oss-120b", "GPT-OSS 120B", ["normal", "reasoning"]),
            Model("glm-4.7", "GLM 4.7", ["normal", "reasoning"]),
        ]
    ),
    
    # ==================== CLOUDFLARE ====================
    "cloudflare": Provider(
        name="Cloudflare",
        endpoint="https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}",
        rate_limit="10K neurons/day",
        models=[
            Model("@cf/meta/llama-4-scout-17b-16e-instruct", "Llama 4 Scout", ["normal", "reasoning"]),
            Model("@cf/meta/llama-3.3-70b-instruct-fp8-fast", "Llama 3.3 70B", ["normal"]),
            Model("@cf/meta/llama-3.1-8b-instruct", "Llama 3.1 8B", ["normal"]),
            Model("@cf/mistralai/mistral-small-3.1-24b-instruct", "Mistral Small 3.1", ["normal"]),
            Model("@cf/google/gemma-3-12b-it", "Gemma 3 12B", ["normal"]),
            Model("@cf/openai/gpt-oss-120b", "GPT-OSS 120B", ["normal", "reasoning"]),
            Model("@cf/openai/gpt-oss-20b", "GPT-OSS 20B", ["normal"]),
        ]
    ),
    
    # ==================== HUGGINGFACE ====================
    "huggingface": Provider(
        name="HuggingFace",
        endpoint="https://router.huggingface.co/v1/chat/completions",
        rate_limit="~50 calls/day",
        models=[
            Model("deepseek-ai/DeepSeek-R1", "DeepSeek R1", ["reasoning"]),
            Model("deepseek-ai/DeepSeek-R1-0528", "DeepSeek R1 0528", ["reasoning"]),
            Model("deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", "DeepSeek R1 Distill 7B", ["reasoning"]),
            Model("deepseek-ai/DeepSeek-R1-Distill-Llama-70B", "DeepSeek R1 Distill 70B", ["reasoning"]),
            Model("meta-llama/Meta-Llama-3.1-8B-Instruct", "Llama 3.1 8B", ["normal"]),
            Model("mistralai/Mistral-7B-Instruct-v0.3", "Mistral 7B", ["normal"]),
            Model("HuggingFaceH4/zephyr-7b-beta", "Zephyr 7B", ["normal"]),
        ]
    ),
    
    # ==================== COHERE ====================
    "cohere": Provider(
        name="Cohere",
        endpoint="https://api.cohere.ai/v2/chat",
        rate_limit="1000 calls/month",
        models=[
            Model("command-a", "Command A", ["normal"]),
            Model("command-r-plus-08-2024", "Command R+", ["normal", "search"]),
            Model("command-r-08-2024", "Command R", ["normal"]),
            Model("command-r7b-12-2024", "Command R 7B", ["normal"]),
        ]
    ),
    
    # ==================== SILICONFLOW ====================
    "siliconflow": Provider(
        name="SiliconFlow",
        endpoint="https://api.siliconflow.cn/v1/chat/completions",
        rate_limit="varies",
        models=[
            Model("Qwen/Qwen2.5-7B-Instruct", "Qwen 2.5 7B", ["normal"]),
            Model("Qwen/Qwen2.5-Coder-7B-Instruct", "Qwen 2.5 Coder 7B", ["normal"]),
            Model("THUDM/glm-4-9b-chat", "GLM 4 9B", ["normal"]),
        ]
    ),
    
    # ==================== ROUTEWAY ====================
    "routeway": Provider(
        name="Routeway",
        endpoint="https://api.routeway.ai/v1/chat/completions",
        rate_limit="varies",
        models=[
            Model("glm-4.6:free", "GLM 4.6", ["normal", "reasoning"], 200000, tools=True),
            Model("glm-4.5-air:free", "GLM 4.5 Air", ["normal"]),
            Model("deepseek-r1:free", "DeepSeek R1", ["reasoning"]),
            Model("kimi-k2:free", "Kimi K2", ["normal"]),
            Model("minimax:free", "MiniMax", ["normal"]),
        ]
    ),
    
    # ==================== MLVOCA ====================
    "mlvoca": Provider(
        name="MLVOCA",
        endpoint="https://mlvoca.com/api/generate",
        auth_header="",
        auth_prefix="",
        rate_limit="unlimited",
        models=[
            Model("tinyllama", "TinyLlama", ["normal"]),
            Model("deepseek-r1:1.5b", "DeepSeek R1 1.5B", ["reasoning"]),
        ]
    ),

    # ==================== PUTER ====================
    "puter": Provider(
        name="Puter",
        endpoint="https://api.puter.com/drivers/call",
        rate_limit="Free Tier (Puter.com)",
        models=[
            Model("gpt-4o", "GPT-4o", ["normal"], 128000),
            Model("gpt-4o-mini", "GPT-4o Mini", ["normal"], 128000),
            Model("gpt-4.1-nano", "GPT-4.1 Nano", ["normal"], 128000),
            Model("claude-sonnet-4", "Claude Sonnet 4", ["normal", "reasoning"], 200000),
            Model("claude-3-5-sonnet", "Claude 3.5 Sonnet", ["normal", "reasoning"], 200000),
            Model("google/gemini-2.5-flash", "Gemini 2.5 Flash", ["normal", "reasoning"], 1048576),
            Model("google/gemini-2.5-pro", "Gemini 2.5 Pro", ["normal", "reasoning"], 1048576),
            Model("deepseek/deepseek-r1", "DeepSeek R1", ["reasoning"], 128000),
            Model("deepseek/deepseek-chat", "DeepSeek Chat", ["normal"], 128000),
            Model("x-ai/grok-3", "Grok 3", ["normal", "reasoning"], 131072),
            Model("x-ai/grok-3-mini", "Grok 3 Mini", ["normal"], 131072),
            Model("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B", ["normal"], 131072),
            Model("perplexity/sonar", "Perplexity Sonar", ["search"], 128000),
            Model("perplexity/sonar-pro", "Perplexity Sonar Pro", ["search"], 200000),
        ]
    ),
}

# ============================================================
# SEARCH PROVIDERS
# ============================================================

SEARCH_PROVIDERS = {
    "duckduckgo": {
        "name": "DuckDuckGo",
        "type": "library",  # Uses duckduckgo-search package
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
        ("groq", "llama-3.3-70b-versatile"),
        ("groq", "llama-3.1-8b-instant"),
        ("openrouter", "meta-llama/llama-4-scout:free"),
        ("openrouter", "deepseek/deepseek-chat-v3-0324:free"),
        ("pollinations", "openai"),
        ("pollinations", "gemini"),
        ("cerebras", "llama3.1-8b"),
        ("cloudflare", "@cf/meta/llama-3.1-8b-instruct"),
        ("puter", "gpt-4o-mini"),
    ],
    "reasoning": [
        ("groq", "deepseek-r1-distill-llama-70b"),
        ("groq", "qwen/qwen3-32b"),
        ("groq", "openai/gpt-oss-120b"),
        ("openrouter", "deepseek/deepseek-r1:free"),
        ("openrouter", "deepseek/deepseek-r1-0528:free"),
        ("openrouter", "stepfun/step-3.5-flash:free"),
        ("pollinations", "perplexity-reasoning"),
        ("cerebras", "gpt-oss-120b"),
        ("routeway", "deepseek-r1:free"),
    ],
    "search": [
        ("duckduckgo", None),
        ("tavily", None),
        ("brave", None),
        ("serper", None),
        ("jina", None),
    ],
}

# ============================================================
# LAVALINK NODES (Music Servers)
# ============================================================

LAVALINK_NODES = [
    {
        "identifier": "Serenetia-V4",
        "host": os.getenv("LAVALINK_HOST", "lavalinkv4.serenetia.com"),
        "port": int(os.getenv("LAVALINK_PORT", "443")),
        "password": os.getenv("LAVALINK_PASSWORD", "https://dsc.gg/ajidevserver"),
        "secure": os.getenv("LAVALINK_SECURE", "true").lower() == "true",
        "heartbeat": 30,
        "retries": 3,
    }
]

# Lyrics API
GENIUS_TOKEN = os.getenv("GENIUS_API_KEY")

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_provider(name: str) -> Optional[Provider]:
    """Get provider by name"""
    return PROVIDERS.get(name.lower())

def get_model(provider_name: str, model_id: str) -> Optional[Model]:
    """Get specific model from provider"""
    provider = get_provider(provider_name)
    if provider:
        for model in provider.models:
            if model.id == model_id:
                return model
    return None

def get_models_by_mode(mode: str) -> List[tuple]:
    """Get all models that support a specific mode"""
    results = []
    for provider_name, provider in PROVIDERS.items():
        for model in provider.models:
            if mode in model.modes:
                results.append((provider_name, model))
    return results

def get_api_key(provider_name: str) -> Optional[str]:
    """Get API key for provider"""
    return API_KEYS.get(provider_name.lower())

def is_provider_available(provider_name: str) -> bool:
    """Check if provider has API key configured (or doesn't need one)"""
    provider = get_provider(provider_name)
    if not provider:
        return False
    # MLVOCA and Pollinations (anonymous) don't need keys
    if provider_name in ["mlvoca", "puter"]:
        return True
    if provider_name == "pollinations":
        return True  # Works without key (anonymous mode)
    return bool(get_api_key(provider_name))

def list_available_providers() -> List[str]:
    """List all providers with valid API keys"""
    return [name for name in PROVIDERS.keys() if is_provider_available(name)]
