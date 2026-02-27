const axios = require('axios')
const { API_KEYS, SYSTEM_PROMPTS, FALLBACK_CHAINS } = require('./config')
const { PROVIDERS, isProviderAvailable } = require('./providers')
const { search } = require('./search')

async function openAIRequest(endpoint, apiKey, model, messages, extraHeaders = {}) {
    const headers = { 'Content-Type': 'application/json', ...extraHeaders }
    if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`
    const { data } = await axios.post(endpoint, {
        model, messages, temperature: 0.7, max_tokens: 4096
    }, { headers, timeout: 60000 })
    return data.choices?.[0]?.message?.content || null
}

async function geminiRequest(model, messages) {
    const apiKey = API_KEYS.gemini
    if (!apiKey) return null
    const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`
    const contents = []
    let systemInstruction = null
    for (const msg of messages) {
        if (msg.role === 'system') systemInstruction = msg.content
        else contents.push({ role: msg.role === 'user' ? 'user' : 'model', parts: [{ text: msg.content }] })
    }
    const payload = { contents, generationConfig: { temperature: 0.7, maxOutputTokens: 4096 } }
    if (systemInstruction) payload.systemInstruction = { parts: [{ text: systemInstruction }] }
    const { data } = await axios.post(endpoint, payload, { headers: { 'Content-Type': 'application/json' }, timeout: 60000 })
    return data.candidates?.[0]?.content?.parts?.[0]?.text || null
}

async function cohereRequest(model, messages) {
    const apiKey = API_KEYS.cohere
    if (!apiKey) return null
    const cohereMessages = messages.map(m => ({
        role: m.role === 'assistant' ? 'assistant' : (m.role === 'system' ? 'system' : 'user'),
        content: m.content
    }))
    const { data } = await axios.post('https://api.cohere.ai/v2/chat', {
        model, messages: cohereMessages, temperature: 0.7, max_tokens: 4096
    }, { headers: { 'Authorization': `Bearer ${apiKey}`, 'X-Client-Name': 'wa-bot' }, timeout: 60000 })
    return data.message?.content?.[0]?.text || null
}

async function cloudflareRequest(model, messages) {
    const apiKey = API_KEYS.cloudflare
    const accountId = API_KEYS.cloudflareAccount
    if (!apiKey || !accountId) return null
    const endpoint = `https://api.cloudflare.com/client/v4/accounts/${accountId}/ai/run/${model}`
    const { data } = await axios.post(endpoint, { messages, max_tokens: 4096 }, {
        headers: { 'Authorization': `Bearer ${apiKey}` }, timeout: 60000
    })
    return data.result?.response || null
}

async function mlvocaRequest(model, messages) {
    const prompt = messages[messages.length - 1]?.content || ''
    let sys = messages.find(m => m.role === 'system')?.content || ''
    const { data } = await axios.post('https://mlvoca.com/api/generate', {
        model, prompt: sys ? `${sys}\n\n${prompt}` : prompt, stream: false
    }, { timeout: 60000 })
    return data.response || null
}

async function puterRequest(model, messages) {
    const apiToken = API_KEYS.puter
    if (!apiToken) return null
    let driver = 'openai-completion'
    if (model.startsWith('claude')) driver = 'anthropic'
    else if (model.startsWith('google/') || model.startsWith('gemini')) driver = 'google-vertex'
    else if (model.startsWith('x-ai/') || model.startsWith('grok')) driver = 'xai'
    else if (model.startsWith('deepseek')) driver = 'deepseek'
    else if (model.startsWith('meta-llama') || model.startsWith('llama')) driver = 'together'
    else if (model.startsWith('perplexity')) driver = 'perplexity'
    const { data } = await axios.post('https://api.puter.com/drivers/call', {
        interface: 'puter-chat-completion', driver, test_mode: false,
        method: 'complete', args: { messages, model, stream: false }
    }, { headers: { 'Authorization': `Bearer ${apiToken}`, 'Origin': 'https://puter.com' }, timeout: 90000 })
    return data.result?.message?.content || data.result?.choices?.[0]?.message?.content || null
}

async function tryProvider(providerName, model, messages) {
    const provider = PROVIDERS[providerName]
    if (!provider) return null
    const apiKey = provider.key()
    if (!apiKey && !['pollinations', 'mlvoca'].includes(providerName)) return null
    
    try {
        if (providerName === 'gemini') return await geminiRequest(model, messages)
        if (providerName === 'cohere') return await cohereRequest(model, messages)
        if (providerName === 'cloudflare') return await cloudflareRequest(model, messages)
        if (providerName === 'mlvoca') return await mlvocaRequest(model, messages)
        if (providerName === 'puter') return await puterRequest(model, messages)
        
        const endpoint = typeof provider.endpoint === 'function' ? provider.endpoint(model) : provider.endpoint
        return await openAIRequest(endpoint, apiKey, model, messages, provider.extraHeaders || {})
    } catch (e) {
        console.log(`⚠️ [${providerName}/${model}] failed: ${e.message}`)
        return null
    }
}

async function askAI(userMessage, useSearch = false, selectedProvider = null, selectedModel = null, chatHistory = [], mode = 'normal') {
    const systemPrompt = SYSTEM_PROMPTS[mode] || SYSTEM_PROMPTS.normal
    let messages = [{ role: 'system', content: systemPrompt }]
    
    if (chatHistory?.length > 0) {
        messages = messages.concat(chatHistory.slice(-8))
    }
    
    if (useSearch || mode === 'search') {
        const searchResult = await search(userMessage)
        if (searchResult) {
            messages.push({ role: 'system', content: `Hasil pencarian:\n${searchResult}` })
        }
    }
    
    messages.push({ role: 'user', content: userMessage })
    
    if (selectedProvider && selectedModel && isProviderAvailable(selectedProvider)) {
        const result = await tryProvider(selectedProvider, selectedModel, messages)
        if (result) {
            console.log(`✅ [${selectedProvider}/${selectedModel}]`)
            return result
        }
        console.log(`⚠️ [${selectedProvider}] failed, trying fallback...`)
    }
    
    const chain = FALLBACK_CHAINS[mode] || FALLBACK_CHAINS.normal
    for (const { provider: pName, model } of chain) {
        if (!isProviderAvailable(pName)) continue
        const result = await tryProvider(pName, model, messages)
        if (result) {
            console.log(`✅ [${pName}/${model}]`)
            return result
        }
    }
    
    return 'Maaf, semua provider tidak tersedia saat ini.'
}

module.exports = { askAI, search, PROVIDERS, tryProvider }
