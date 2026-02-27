const { makeWASocket, DisconnectReason, useMultiFileAuthState } = require('baileys')
const pino = require('pino')
const qrcode = require('qrcode-terminal')
const { askAI, search, PROVIDERS } = require('./ai')
const { DEFAULTS } = require('./config')
const { listAvailableProviders } = require('./providers')
const db = require('./database')

// Cache settings in memory (loaded from DB on first access)
const sessionCache = new Map()

async function getSession(userId) {
    if (!sessionCache.has(userId)) {
        // Load from database
        const dbSettings = await db.getSettings(userId)
        
        sessionCache.set(userId, {
            provider: dbSettings?.provider || DEFAULTS.provider,
            model: dbSettings?.model || DEFAULTS.model,
            mode: dbSettings?.mode || DEFAULTS.mode,
        })
    }
    return sessionCache.get(userId)
}

async function saveSession(userId, provider, model, mode) {
    sessionCache.set(userId, { provider, model, mode })
    await db.saveSettings(userId, provider, model, mode)
}

async function handleCommand(from, text) {
    const session = await getSession(from)
    const args = text.trim().split(/\s+/)
    const cmd = args[0].toLowerCase()

    if (cmd === '!help') {
        return `*🤖 Claw AI - WhatsApp Bot*\n\n*Commands:*\n• !help - Bantuan\n• !set - Lihat provider\n• !set <provider> - Lihat model\n• !set <provider> <model> - Pilih\n• !mode normal|search|reasoning\n• !search <query>\n• !clear - Hapus history\n• !stats - Statistik chat\n• !status\n\n*Aktif:* ${session.provider} / ${session.model} / ${session.mode}`
    }

    if (cmd === '!status') {
        const available = listAvailableProviders()
        const totalMessages = await db.getStats(from)
        return `*📊 Status*\n• Provider: ${session.provider}\n• Model: ${session.model}\n• Mode: ${session.mode}\n• Messages: ${totalMessages}\n• Available: ${available.length} providers`
    }

    if (cmd === '!stats') {
        const total = await db.getStats(from)
        return `*📊 Chat Statistics*\n• Total messages: ${total}\n• Database: SQLite\n• Storage: Persistent\n\nGunakan !clear untuk hapus history`
    }

    if (cmd === '!clear') {
        await db.clearHistory(from)
        return '🗑️ History dihapus!\n(Settings tetap tersimpan)'
    }

    if (cmd === '!mode') {
        const mode = args[1]?.toLowerCase()
        if (!mode) return `Mode aktif: *${session.mode}*\nPilihan: normal, search, reasoning`
        if (!['normal', 'search', 'reasoning'].includes(mode)) return '❌ Mode tidak valid.'
        await saveSession(from, session.provider, session.model, mode)
        return `✅ Mode: *${mode}*`
    }

    if (cmd === '!search') {
        const query = args.slice(1).join(' ')
        if (!query) return '❌ Contoh: !search cuaca jakarta'
        const result = await search(query)
        return result ? `🔍 *Hasil:*\n\n${result}` : '❌ Tidak ada hasil.'
    }

    if (cmd === '!set' && args.length === 1) {
        let reply = '*⚙️ Provider Tersedia:*\n\n'
        for (const [name, p] of Object.entries(PROVIDERS)) {
            const apiKey = p.key()
            if (!apiKey && !['pollinations', 'mlvoca'].includes(name)) continue
            const active = session.provider === name ? ' ✅' : ''
            reply += `*${name}*${active} (${p.models.length} model)\n`
        }
        return reply + '\nKetik !set <provider> untuk lihat model'
    }

    if (cmd === '!set' && args.length === 2) {
        const providerName = args[1].toLowerCase()
        const provider = PROVIDERS[providerName]
        if (!provider) return `❌ Provider tidak ada: ${providerName}`
        let reply = `*📋 Model di ${providerName}:*\n\n`
        provider.models.slice(0, 20).forEach((m, i) => {
            const active = (session.provider === providerName && session.model === m) ? ' ✅' : ''
            reply += `${i + 1}. ${m}${active}\n`
        })
        if (provider.models.length > 20) reply += `\n...dan ${provider.models.length - 20} lainnya`
        return reply + `\nGunakan: !set ${providerName} <model>`
    }

    if (cmd === '!set' && args.length >= 3) {
        const providerName = args[1].toLowerCase()
        const modelName = args.slice(2).join(' ')
        const provider = PROVIDERS[providerName]
        if (!provider) return `❌ Provider tidak ada: ${providerName}`
        const validModel = provider.models.find(m => m === modelName || m.includes(modelName))
        if (!validModel) return `❌ Model tidak ada: ${modelName}\nKetik !set ${providerName} untuk daftar.`
        
        // SAVE WITHOUT CLEARING HISTORY! ✅
        await saveSession(from, providerName, validModel, session.mode)
        
        return `✅ *Provider & Model Updated!*\n• Provider: ${providerName}\n• Model: ${validModel}\n• History: TETAP TERSIMPAN ✅`
    }

    return null
}

let reconnectAttempts = 0
const MAX_RECONNECT = 10

async function connectWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('./session')

    const sock = makeWASocket({
        auth: state,
        logger: pino({ level: 'silent' }),
        browser: ['Claw AI', 'Chrome', '1.0.0'],
    })

    sock.ev.on('creds.update', saveCreds)

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update

        if (qr) {
            console.log('\n📱 Scan QR Code ini:\n')
            qrcode.generate(qr, { small: true })
            return
        }

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut

            if (statusCode === DisconnectReason.loggedOut) {
                console.log('❌ Logged out! Hapus session dan scan ulang.')
                return
            }

            reconnectAttempts++
            if (reconnectAttempts > MAX_RECONNECT) {
                console.log(`❌ Gagal reconnect ${MAX_RECONNECT}x, berhenti.`)
                return
            }

            const delay = Math.min(3000 * reconnectAttempts, 30000)
            console.log(`🔄 Reconnecting (${reconnectAttempts}/${MAX_RECONNECT}) in ${delay/1000}s...`)
            setTimeout(connectWhatsApp, delay)

        } else if (connection === 'open') {
            reconnectAttempts = 0
            console.log('✅ WhatsApp Connected!')
            console.log(`📦 Providers: ${listAvailableProviders().join(', ')}`)
        }
    })

    sock.ev.on('messages.upsert', async ({ messages }) => {
        const msg = messages[0]
        if (!msg?.message || msg.key.fromMe) return

        const from = msg.key.remoteJid
        const text = msg.message?.conversation || msg.message?.extendedTextMessage?.text || ''
        if (!text.trim()) return

        console.log(`📨 [${from}]: ${text}`)

        try {
            if (text.startsWith('!')) {
                const reply = await handleCommand(from, text)
                if (reply) { await sock.sendMessage(from, { text: reply }); return }
            }

            const session = await getSession(from)
            
            // Load history from database
            const history = await db.getHistory(from, 10)
            
            // Add user message to database
            await db.addMessage(from, 'user', text)

            const reply = await askAI(text, session.mode === 'search', session.provider, session.model, history, session.mode)

            // Add AI response to database
            await db.addMessage(from, 'assistant', reply)
            
            await sock.sendMessage(from, { text: reply })
            console.log(`🤖 [${session.provider}/${session.model}]: ${reply.substring(0, 80)}...`)
        } catch (e) {
            console.error('Error:', e.message)
            await sock.sendMessage(from, { text: '❌ Terjadi kesalahan.' })
        }
    })

    return sock
}

console.log('🚀 Starting Claw AI WhatsApp Bot...')
connectWhatsApp()
