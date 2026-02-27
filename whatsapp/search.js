const axios = require('axios')
const { API_KEYS } = require('./config')

async function search(query, engine = 'duckduckgo', maxResults = 5) {
    try {
        if (engine === 'duckduckgo') return await searchDDG(query, maxResults)
        if (engine === 'tavily') return await searchTavily(query, maxResults)
        if (engine === 'brave') return await searchBrave(query, maxResults)
        if (engine === 'serper') return await searchSerper(query, maxResults)
        if (engine === 'jina') return await searchJina(query)
        return await searchDDG(query, maxResults)
    } catch (e) {
        console.error(`Search error (${engine}):`, e.message)
        return null
    }
}

async function searchDDG(query, maxResults = 5) {
    const url = `https://api.duckduckgo.com/?q=${encodeURIComponent(query)}&format=json&no_html=1`
    const { data } = await axios.get(url, { timeout: 10000 })
    const results = []
    if (data.Abstract) results.push(`📌 ${data.Abstract}`)
    for (const t of (data.RelatedTopics || []).slice(0, maxResults)) {
        if (t.Text) results.push(`• ${t.Text}`)
    }
    return results.length > 0 ? results.join('\n\n') : null
}

async function searchTavily(query, maxResults = 5) {
    if (!API_KEYS.tavily) return await searchDDG(query, maxResults)
    const { data } = await axios.post('https://api.tavily.com/search', {
        api_key: API_KEYS.tavily, query, max_results: maxResults, include_answer: true
    }, { timeout: 15000 })
    const results = []
    if (data.answer) results.push(`📌 ${data.answer}`)
    for (const r of data.results || []) {
        results.push(`• *${r.title}*\n  ${r.content.slice(0, 200)}...\n  🔗 ${r.url}`)
    }
    return results.length > 0 ? results.join('\n\n') : null
}

async function searchBrave(query, maxResults = 5) {
    if (!API_KEYS.brave) return await searchDDG(query, maxResults)
    const { data } = await axios.get('https://api.search.brave.com/res/v1/web/search', {
        headers: { 'X-Subscription-Token': API_KEYS.brave },
        params: { q: query, count: maxResults }, timeout: 15000
    })
    const results = []
    for (const r of data.web?.results || []) {
        results.push(`• *${r.title}*\n  ${r.description}\n  🔗 ${r.url}`)
    }
    return results.length > 0 ? results.join('\n\n') : null
}

async function searchSerper(query, maxResults = 5) {
    if (!API_KEYS.serper) return await searchDDG(query, maxResults)
    const { data } = await axios.post('https://google.serper.dev/search',
        { q: query, num: maxResults },
        { headers: { 'X-API-KEY': API_KEYS.serper }, timeout: 15000 }
    )
    const results = []
    if (data.answerBox) results.push(`📌 ${data.answerBox.answer || data.answerBox.snippet}`)
    for (const r of data.organic || []) {
        results.push(`• *${r.title}*\n  ${r.snippet}\n  🔗 ${r.link}`)
    }
    return results.length > 0 ? results.join('\n\n') : null
}

async function searchJina(query) {
    const { data } = await axios.get(`https://s.jina.ai/${encodeURIComponent(query)}`, { timeout: 30000 })
    return data?.slice(0, 2000) || null
}

module.exports = { search }
