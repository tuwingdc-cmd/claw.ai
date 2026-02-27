const { API_KEYS } = require('./config')

const PROVIDERS = {
    groq: {
        name: 'Groq',
        endpoint: 'https://api.groq.com/openai/v1/chat/completions',
        key: () => API_KEYS.groq,
        rateLimit: '30 RPM (70B), 60 RPM (8B)',
        models: [
            'compound-beta', 'compound-beta-mini',
            'llama-3.3-70b-versatile', 'llama-3.1-8b-instant',
            'openai/gpt-oss-120b', 'openai/gpt-oss-20b',
            'meta-llama/llama-4-maverick-17b-128e-instruct',
            'meta-llama/llama-4-scout-17b-16e-instruct',
            'qwen-qwq-32b', 'deepseek-r1-distill-llama-70b',
            'moonshotai/kimi-k2-instruct-0905', 'qwen/qwen-3-32b',
            'whisper-large-v3', 'whisper-large-v3-turbo',
        ],
    },
    openrouter: {
        name: 'OpenRouter',
        endpoint: 'https://openrouter.ai/api/v1/chat/completions',
        key: () => API_KEYS.openrouter,
        extraHeaders: { 'HTTP-Referer': 'https://wa-bot.local', 'X-Title': 'WA AI Bot' },
        rateLimit: '20 RPM, 50 RPD (free)',
        models: [
            'openrouter/free',
            'meta-llama/llama-4-maverick:free', 'meta-llama/llama-4-scout:free',
            'meta-llama/llama-3.3-70b-instruct:free',
            'deepseek/deepseek-chat-v3-0324:free', 'deepseek/deepseek-v3-base:free',
            'deepseek/deepseek-r1-zero:free',
            'mistralai/mistral-small-3.1-24b-instruct:free',
            'nvidia/llama-3.1-nemotron-nano-8b-v1:free',
            'qwen/qwen3-coder:free', 'stepfun/step-3.5-flash:free',
            'google/gemini-2.5-pro-exp-03-25:free',
            'qwen/qwen3-next-80b-a3b-instruct:free',
            'nvidia/nemotron-3-nano-30b-a3b:free',
            'arcee-ai/trinity-large-preview:free', 'arcee-ai/trinity-mini:free',
            'zhipuai/glm-4.5-air:free',
            'openrouter/optimus-alpha', 'openrouter/quasar-alpha',
        ],
    },
    pollinations: {
        name: 'Pollinations',
        endpoint: 'https://gen.pollinations.ai/v1/chat/completions',
        key: () => API_KEYS.pollinations || null,
        rateLimit: '1/15s (anon), unlimited (sk_)',
        models: [
            'openai', 'openai-fast', 'openai-large',
            'gemini', 'gemini-fast', 'gemini-large', 'gemini-search',
            'deepseek', 'claude', 'claude-fast', 'claude-large',
            'mistral', 'grok', 'qwen-coder', 'kimi', 'glm', 'minimax',
            'perplexity-fast', 'perplexity-reasoning',
        ],
    },
    gemini: {
        name: 'Google Gemini',
        endpoint: (model) => `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`,
        key: () => API_KEYS.gemini,
        rateLimit: '5-15 RPM (free)',
        models: [
            'gemini-2.5-pro', 'gemini-2.5-flash',
            'gemini-2.5-flash-lite-preview-06-17',
            'gemma-3-27b-it', 'gemma-2-9b-it',
        ],
    },
    cerebras: {
        name: 'Cerebras',
        endpoint: 'https://api.cerebras.ai/v1/chat/completions',
        key: () => API_KEYS.cerebras,
        rateLimit: '30 RPM, 1M tokens/day',
        models: [
            'llama3.1-8b', 'llama-3.3-70b',
            'qwen-3-32b', 'qwen-3-235b-a22b-instruct-2507',
            'gpt-oss-120b', 'zai-glm-4.6', 'zai-glm-4.7',
        ],
    },
    sambanova: {
        name: 'SambaNova',
        endpoint: 'https://api.sambanova.ai/v1/chat/completions',
        key: () => API_KEYS.sambanova,
        rateLimit: 'Free tier',
        models: [
            'Meta-Llama-3.1-8B-Instruct', 'Meta-Llama-3.3-70B-Instruct',
            'Llama-4-Scout-17B-16E-Instruct', 'Llama-4-Maverick-17B-128E-Instruct',
            'DeepSeek-R1', 'DeepSeek-R1-Distill-Llama-70B', 'DeepSeek-V3-0324',
            'Qwen3-32B', 'QwQ-32B', 'gpt-oss-120b',
        ],
    },
    cloudflare: {
        name: 'Cloudflare',
        endpoint: (model) => `https://api.cloudflare.com/client/v4/accounts/${API_KEYS.cloudflareAccount}/ai/run/${model}`,
        key: () => API_KEYS.cloudflare,
        rateLimit: '10K neurons/day',
        models: [
            '@cf/meta/llama-4-scout-17b-16e-instruct',
            '@cf/meta/llama-3.3-70b-instruct-fp8-fast',
            '@cf/meta/llama-3.1-8b-instruct',
            '@cf/mistralai/mistral-small-3.1-24b-instruct',
            '@cf/google/gemma-3-12b-it',
            '@cf/openai/gpt-oss-120b', '@cf/openai/gpt-oss-20b',
        ],
    },
    huggingface: {
        name: 'HuggingFace',
        endpoint: 'https://router.huggingface.co/v1/chat/completions',
        key: () => API_KEYS.huggingface,
        rateLimit: '~50 calls/day',
        models: [
            'deepseek-ai/DeepSeek-R1', 'deepseek-ai/DeepSeek-R1-0528',
            'deepseek-ai/DeepSeek-R1-Distill-Qwen-7B',
            'deepseek-ai/DeepSeek-R1-Distill-Llama-70B',
            'meta-llama/Meta-Llama-3.1-8B-Instruct',
            'mistralai/Mistral-7B-Instruct-v0.3',
            'HuggingFaceH4/zephyr-7b-beta',
        ],
    },
    cohere: {
        name: 'Cohere',
        endpoint: 'https://api.cohere.ai/v2/chat',
        key: () => API_KEYS.cohere,
        rateLimit: '1000 calls/month',
        models: [
            'command-a-08-2025', 'command-r-plus-08-2024',
            'command-r-08-2024', 'command-r7b-12-2024',
        ],
    },
    siliconflow: {
        name: 'SiliconFlow',
        endpoint: 'https://api.siliconflow.com/v1/chat/completions',
        key: () => API_KEYS.siliconflow,
        rateLimit: '100 RPD (free)',
        models: [
            'Qwen/Qwen2.5-7B-Instruct', 'Qwen/Qwen2.5-Coder-7B-Instruct',
            'THUDM/GLM-4-9B-0414',
            'deepseek-ai/DeepSeek-R1-Distill-Qwen-7B',
            'deepseek-ai/DeepSeek-R1-Distill-Qwen-14B',
            'deepseek-ai/DeepSeek-R1-Distill-Qwen-32B',
            'Qwen/QwQ-32B',
            'deepseek-ai/DeepSeek-R1-0528', 'deepseek-ai/DeepSeek-R1',
            'deepseek-ai/DeepSeek-V3-0324',
            'Qwen/Qwen2.5-Coder-32B-Instruct', 'Qwen/Qwen3-32B',
        ],
    },
    routeway: {
        name: 'Routeway',
        endpoint: 'https://api.routeway.ai/v1/chat/completions',
        key: () => API_KEYS.routeway,
        rateLimit: '20 RPM, 200 RPD',
        models: [
            'glm-4.6:free', 'glm-4.5-air:free',
            'deepseek-r1:free', 'minimax-m2:free', 'kimi-k2:free',
            'deepseek-v3.1:free', 'llama-3.3-70b-instruct:free',
            'mistral-small-3:free',
        ],
    },
    mlvoca: {
        name: 'MLVOCA',
        endpoint: 'https://mlvoca.com/api/generate',
        key: () => null,
        rateLimit: 'unlimited',
        models: ['tinyllama', 'deepseek-r1:1.5b'],
    },
    puter: {
        name: 'Puter',
        endpoint: 'https://api.puter.com/drivers/call',
        key: () => API_KEYS.puter,
        rateLimit: 'Free Tier',
        models: [
            'gpt-4o', 'gpt-4o-mini', 'gpt-4.1-nano',
            'claude-sonnet-4', 'claude-3-5-sonnet',
            'google/gemini-2.5-flash', 'google/gemini-2.5-pro',
            'deepseek/deepseek-r1', 'deepseek/deepseek-chat',
            'x-ai/grok-3', 'x-ai/grok-3-mini',
            'meta-llama/llama-3.3-70b-instruct',
            'perplexity/sonar', 'perplexity/sonar-pro',
        ],
    },
}

function isProviderAvailable(name) {
    const p = PROVIDERS[name]
    if (!p) return false
    if (['pollinations', 'mlvoca'].includes(name)) return true
    return !!p.key()
}

function listAvailableProviders() {
    return Object.keys(PROVIDERS).filter(isProviderAvailable)
}

module.exports = { PROVIDERS, isProviderAvailable, listAvailableProviders }
