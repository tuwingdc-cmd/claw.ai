/**
 * AI Provider Bridge for WhatsApp Bot
 * Mirrors providers from claw.ai/config.py
 */

const axios = require('axios')

// ============================================================
// PROVIDER CONFIGS
// ============================================================

const PROVIDERS = {
    groq: {
        endpoint: 'https://api.groq.com/openai/v1/chat/completions',
        key: () => process.env.GROQ_API_KEY,
        models: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'deepseek-r1-distill-llama-70b'],
        defaultModel: 'llama-3.3-70b-versatile',
    },
    openrouter: {
        endpoint: 'https://openrouter.ai/api/v1/chat/completions',
        key: () => process.env.OPENROUTER_API_KEY,
        models: ['meta-llama/llama-3.3-70b-instruct:free', 'deepseek/deepseek-r1:free', 'openrouter/free'],
        defaultModel: 'meta-llama/llama-3.3-70b-instruct:free',
        extraHeaders: {
            'HTTP-Referer': 'https://wa-bot.local',
            'X-Title': 'WhatsApp AI Bot'
        }
    },
    gemini: {
        endpoint: (model) => `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`,
        key: () => process.env.GEMINI_API_KEY,
        models: ['gemini-2.0-flash', 'gemini-2.5-flash'],
        defaultModel: 'gemini-2.0-flash',
        special: 'gemini'
    },
    cerebras: {
        endpoint: 'https://api.cerebras.ai/v1/chat/completions',
        key: () => process.env.CEREBRAS_API_KEY,
        models: ['llama3.3-70b', 'llama3.1-8b'],
        defaultModel: 'llama3.3-70b',
    },
    sambanova: {
        endpoint: 'https://api.sambanova.ai/v1/chat/completions',
        key: () => process.env.SAMBANOVA_API_KEY,
        models: ['Meta-Llama-3.3-70B-Instruct', 'DeepSeek-R1'],
        defaultModel: 'Meta-Llama-3.3-70B-Instruct',
    },
    pollinations: {
        endpoint: 'https://gen.pollinations.ai/v1/chat/completions',
        key: () => process.env.POLLINATIONS_API_KEY || null,
        models: ['openai', 'gemini', 'claude', 'deepseek', 'mistral'],
        defaultModel: 'openai',
    },
    cohere: {
        endpoint: 'https://api.cohere.ai/v2/chat',
        key: () => process.env.COHERE_API_KEY,
        models: ['command-r-plus-08-2024', 'command-r-08-2024'],
        defaultModel: 'command-r-plus-08-2024',
        special: 'cohere'
    },
    siliconflow: {
        endpoint: 'https://api.siliconflow.com/v1/chat/completions',
        key: () => process.env.SILICONFLOW_API_KEY,
        models: ['Qwen/Qwen2.5-72B-Instruct', 'deepseek-ai/DeepSeek-V3'],
        defaultModel: 'Qwen/Qwen2.5-72B-Instruct',
    },
    cloudflare: {
        endpoint: (model) => `https://api.cloudflare.com/client/v4/accounts/${process.env.CLOUDFLARE_ACCOUNT_ID}/ai/run/${model}`,
        key: () => process.env.CLOUDFLARE_API_TOKEN,
        models: ['@cf/meta/llama-3.1-8b-instruct', '@cf/meta/llama-3.3-70b-instruct-fp8-fast'],
        defaultModel: '@cf/meta/llama-3.1-8b-instruct',
        special: 'cloudflare'
    },
    huggingface: {
        endpoint: 'https://router.huggingface.co/v1/chat/completions',
        key: () => process.env.HUGGINGFACE_TOKEN,
        models: ['meta-llama/Llama-3.3-70B-Instruct', 'Qwen/Qwen2.5-72B-Instruct'],
        defaultModel: 'meta-llama/Llama-3.3-70B-Instruct',
    },
}

// Fallback chain - urutan provider yang dicoba
const FALLBACK_CHAIN = [
    { provider: 'groq',        model: 'llama-3.3-70b-versatile' },
    { provider: 'sambanova',   model: 'Meta-Llama-3.3-70B-Instruct' },
    { provider: 'cerebras',    model: 'llama3.3-70b' },
    { provider: 'openrouter',  model: 'meta-llama/llama-3.3-70b-instruct:free' },
    { provider: 'pollinations', model: 'openai' },
    { provider: 'cloudflare',  model: '@cf/meta/llama-3.1-8b-instruct' },
    { provider: 'huggingface', model: 'meta-llama/Llama-3.3-70B-Instruct' },
]

// ============================================================
// OPENAI-COMPATIBLE REQUEST
// ============================================================

async function openAIRequest(endpoint, apiKey, model, messages, extraHeaders = {}) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
        ...extraHeaders
    }
    const res = await axios.post(endpoint, {
        model,
        messages,
        max_tokens: 1024,
        temperature: 0.7,
    }, { headers, timeout: 30000 })

    return res.data.choices[0].message.content
}

// ============================================================
// SPECIAL PROVIDERS
// ============================================================

async function geminiRequest(model, messages) {
    const apiKey = process.env.GEMINI_API_KEY
    const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`

    const contents = []
    let systemInstruction = null

    for (const msg of messages) {
        if (msg.role === 'system') {
            systemInstruction = msg.content
        } else {
            contents.push({
                role: msg.role === 'user' ? 'user' : 'model',
                parts: [{ text: msg.content }]
            })
        }
    }

    const payload = { contents, generationConfig: { maxOutputTokens: 1024 } }
    if (systemInstruction) payload.systemInstruction = { parts: [{ text: systemInstruction }] }

    const res = await axios.post(endpoint, payload, {
        headers: { 'Content-Type': 'application/json' },
        timeout: 30000
    })
    return res.data.candidates[0].content.parts[0].text
}

async function cohereRequest(model, messages) {
    const res = await axios.post('https://api.cohere.ai/v2/chat', {
        model,
        messages,
        max_tokens: 1024,
    }, {
        headers: {
            'Authorization': `Bearer ${process.env.COHERE_API_KEY}`,
            'Content-Type': 'application/json'
        },
        timeout: 30000
    })
    return res.data.message.content[0].text
}

async function cloudflareRequest(model, messages) {
    const accountId = process.env.CLOUDFLARE_ACCOUNT_ID
    const apiKey = process.env.CLOUDFLARE_API_TOKEN
    const endpoint = `https://api.cloudflare.com/client/v4/accounts/${accountId}/ai/run/${model}`

    const res = await axios.post(endpoint, { messages, max_tokens: 1024 }, {
        headers: {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
        },
        timeout: 30000
    })
    return res.data.result.response
}

// ============================================================
// SEARCH ENGINE
// ============================================================

async function searchDuckDuckGo(query) {
    try {
        const res = await axios.get(`https://api.duckduckgo.com/?q=${encodeURIComponent(query)}&format=json&no_html=1`, {
            timeout: 10000
        })
        const data = res.data
        let results = []

        if (data.AbstractText) results.push(data.AbstractText)
        if (data.RelatedTopics) {
            data.RelatedTopics.slice(0, 3).forEach(t => {
                if (t.Text) results.push(t.Text)
            })
        }
        return results.length > 0 ? results.join('\n\n') : null
    } catch (e) {
        return null
    }
}

async function searchSerper(query) {
    try {
        const res = await axios.post('https://google.serper.dev/search', { q: query, num: 3 }, {
            headers: {
                'X-API-KEY': process.env.SERPER_API_KEY,
                'Content-Type': 'application/json'
            },
            timeout: 10000
        })
        return res.data.organic?.slice(0, 3).map(r => `${r.title}: ${r.snippet}`).join('\n\n')
    } catch (e) {
        return null
    }
}

async function searchTavily(query) {
    try {
        const res = await axios.post('https://api.tavily.com/search', {
            api_key: process.env.TAVILY_API_KEY,
            query,
            max_results: 3
        }, { timeout: 10000 })
        return res.data.results?.slice(0, 3).map(r => `${r.title}: ${r.content}`).join('\n\n')
    } catch (e) {
        return null
    }
}

async function search(query) {
    // Coba search engine satu per satu
    if (process.env.TAVILY_API_KEY) {
        const result = await searchTavily(query)
        if (result) return result
    }
    if (process.env.SERPER_API_KEY) {
        const result = await searchSerper(query)
        if (result) return result
    }
    return await searchDuckDuckGo(query)
}

// ============================================================
// MAIN AI FUNCTION (dengan fallback + search)
// ============================================================

const SYSTEM_PROMPT = `Kamu adalah asisten AI yang membantu bernama Vee. 
Jawab dengan bahasa yang sama dengan pengguna. 
Berikan jawaban yang informatif, ramah, dan ringkas.`

async function askAI(userMessage, useSearch = false) {
    let messages = [{ role: 'system', content: SYSTEM_PROMPT }]

    // Jika mode search, cari dulu lalu inject ke context
    if (useSearch) {
        const searchResult = await search(userMessage)
        if (searchResult) {
            messages.push({
                role: 'system',
                content: `Hasil pencarian web untuk "${userMessage}":\n\n${searchResult}\n\nGunakan informasi ini untuk menjawab.`
            })
        }
    }

    messages.push({ role: 'user', content: userMessage })

    // Coba satu per satu sesuai fallback chain
    for (const { provider: providerName, model } of FALLBACK_CHAIN) {
        const provider = PROVIDERS[providerName]
        const apiKey = provider.key()

        // Skip kalau tidak ada API key (kecuali pollinations)
        if (!apiKey && providerName !== 'pollinations') continue

        try {
            let content = null

            if (provider.special === 'gemini') {
                content = await geminiRequest(model, messages)
            } else if (provider.special === 'cohere') {
                content = await cohereRequest(model, messages)
            } else if (provider.special === 'cloudflare') {
                content = await cloudflareRequest(model, messages)
            } else {
                const endpoint = typeof provider.endpoint === 'function'
                    ? provider.endpoint(model)
                    : provider.endpoint
                content = await openAIRequest(endpoint, apiKey, model, messages, provider.extraHeaders || {})
            }

            if (content) {
                console.log(`✅ [${providerName}/${model}] responded`)
                return content
            }
        } catch (e) {
            console.log(`⚠️ [${providerName}] failed: ${e.message}`)
            continue
        }
    }

    return 'Maaf, semua provider AI sedang tidak tersedia. Coba lagi nanti.'
}

module.exports = { askAI, search }
