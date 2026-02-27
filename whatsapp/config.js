require('dotenv').config({ path: '../.env' })

const API_KEYS = {
    groq: process.env.GROQ_API_KEY,
    openrouter: process.env.OPENROUTER_API_KEY,
    pollinations: process.env.POLLINATIONS_API_KEY,
    gemini: process.env.GEMINI_API_KEY,
    cerebras: process.env.CEREBRAS_API_KEY,
    sambanova: process.env.SAMBANOVA_API_KEY,
    cloudflare: process.env.CLOUDFLARE_API_TOKEN,
    cloudflareAccount: process.env.CLOUDFLARE_ACCOUNT_ID,
    huggingface: process.env.HUGGINGFACE_TOKEN,
    cohere: process.env.COHERE_API_KEY,
    siliconflow: process.env.SILICONFLOW_API_KEY,
    routeway: process.env.ROUTEWAY_API_KEY,
    tavily: process.env.TAVILY_API_KEY,
    brave: process.env.BRAVE_API_KEY,
    serper: process.env.SERPER_API_KEY,
    puter: process.env.PUTER_API_KEY,
}

const DEFAULTS = {
    provider: process.env.DEFAULT_PROVIDER || 'groq',
    model: process.env.DEFAULT_MODEL || 'llama-3.3-70b-versatile',
    mode: 'normal',
    searchEngine: 'duckduckgo',
}

const SYSTEM_PROMPTS = {
    normal: 'Kamu adalah asisten AI bernama Vee. Jawab dengan bahasa yang sama dengan pengguna. Berikan jawaban yang helpful, akurat, dan friendly.',
    reasoning: 'Kamu adalah asisten AI bernama Vee dengan kemampuan reasoning tinggi. Gunakan pendekatan step-by-step untuk masalah kompleks. Jawab dengan bahasa yang sama dengan pengguna.',
    search: 'Kamu adalah asisten AI bernama Vee dengan akses informasi terkini. Gunakan hasil pencarian untuk menjawab. Sebutkan sumber jika relevan. Jawab dengan bahasa yang sama dengan pengguna.',
}

const FALLBACK_CHAINS = {
    normal: [
        { provider: 'groq', model: 'llama-3.3-70b-versatile' },
        { provider: 'groq', model: 'llama-3.1-8b-instant' },
        { provider: 'cerebras', model: 'llama-3.3-70b' },
        { provider: 'sambanova', model: 'Meta-Llama-3.3-70B-Instruct' },
        { provider: 'openrouter', model: 'openrouter/free' },
        { provider: 'openrouter', model: 'meta-llama/llama-3.3-70b-instruct:free' },
        { provider: 'pollinations', model: 'openai' },
        { provider: 'pollinations', model: 'gemini' },
        { provider: 'cloudflare', model: '@cf/meta/llama-3.1-8b-instruct' },
        { provider: 'puter', model: 'gpt-4o-mini' },
        { provider: 'mlvoca', model: 'tinyllama' },
    ],
    reasoning: [
        { provider: 'groq', model: 'deepseek-r1-distill-llama-70b' },
        { provider: 'groq', model: 'qwen-qwq-32b' },
        { provider: 'groq', model: 'openai/gpt-oss-120b' },
        { provider: 'cerebras', model: 'gpt-oss-120b' },
        { provider: 'sambanova', model: 'DeepSeek-R1' },
        { provider: 'openrouter', model: 'deepseek/deepseek-r1-zero:free' },
        { provider: 'pollinations', model: 'perplexity-reasoning' },
        { provider: 'routeway', model: 'deepseek-r1:free' },
    ],
    search: [
        { provider: 'duckduckgo', model: null },
        { provider: 'tavily', model: null },
        { provider: 'brave', model: null },
        { provider: 'serper', model: null },
    ],
}

module.exports = { API_KEYS, DEFAULTS, SYSTEM_PROMPTS, FALLBACK_CHAINS }
