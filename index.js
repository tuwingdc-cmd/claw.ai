/**
 * Claw AI - WhatsApp Bot
 * Integrated with all providers from claw.ai
 */

const { default: makeWASocket, useMultiFileAuthState } = require('@whiskeysockets/baileys')
const qrcode = require('qrcode-terminal')
const { askAI, search } = require('./ai')
require('dotenv').config({ path: '../.env' })

// ============================================================
// SESSION MANAGEMENT (per user)
// ============================================================

const sessions = new Map() // userId -> { history, mode, lastActivity }

function getSession(userId) {
    if (!sessions.has(userId)) {
        sessions.set(userId, {
            history: [],
            mode: 'normal', // normal | search | reasoning
            lastActivity: Date.now()
        })
    }
    return sessions.get(userId)
}

function addToHistory(userId, role, content) {
    const session = getSession(userId)
    session.history.push({ role, content })
    session.lastActivity = Date.now()
    // Batasi history 10 pesan terakhir
    if (session.history.length > 10) session.history.shift()
}

// Bersihkan session tidak aktif (>1 jam)
setInterval(() => {
    const now = Date.now()
    for (const [userId, session] of sessions.entries()) {
        if (now - session.lastActivity > 3600000) sessions.delete(userId)
    }
}, 600000)

// ============================================================
// COMMAND HANDLER
// ============================================================

async function handleCommand(sock, from, text) {
    const cmd = text.toLowerCase().trim()
    const session = getSession(from)

    if (cmd === '!help' || cmd === '/help') {
        return `*🤖 Claw AI - WhatsApp Bot*

*Commands:*
• \`!help\` - Tampilkan bantuan ini
• \`!mode normal\` - Mode chat biasa
• \`!mode search\` - Mode pencarian web
• \`!clear\` - Hapus riwayat chat
• \`!status\` - Cek status bot
• \`!search <query>\` - Cari di web langsung

*Mode aktif:* ${session.mode}
*History:* ${session.history.length} pesan

Kirim pesan apapun untuk chat dengan AI! 💬`
    }

    if (cmd.startsWith('!mode ')) {
        const mode = cmd.replace('!mode ', '').trim()
        if (['normal', 'search', 'reasoning'].includes(mode)) {
            session.mode = mode
            return `✅ Mode diubah ke: *${mode}*`
        }
        return '❌ Mode tidak valid. Pilih: normal, search, reasoning'
    }

    if (cmd === '!clear') {
        session.history = []
        return '🗑️ Riwayat chat dihapus!'
    }

    if (cmd === '!status') {
        return `*📊 Status Bot*
• Status: ✅ Online
• Mode: ${session.mode}
• History: ${session.history.length} pesan
• Provider: Groq → SambaNova → Cerebras → (fallback)`
    }

    if (cmd.startsWith('!search ')) {
        const query = text.replace(/!search /i, '').trim()
        const result = await search(query)
        return result ? `🔍 *Hasil pencarian:*\n\n${result}` : '❌ Tidak ada hasil pencarian.'
    }

    return null // bukan command
}

// ============================================================
// MAIN BOT
// ============================================================

async function startBot() {
    const { state, saveCreds } = await useMultiFileAuthState('auth')
    const sock = makeWASocket({ auth: state })

    sock.ev.on('connection.update', ({ connection, qr, lastDisconnect }) => {
        if (qr) {
            console.log('\n📱 Scan QR ini dengan WhatsApp:\n')
            qrcode.generate(qr, { small: true })
        }
        if (connection === 'open') {
            console.log('✅ WhatsApp Bot Connected!')
        }
        if (connection === 'close') {
            console.log('🔄 Reconnecting...')
            setTimeout(startBot, 3000)
        }
    })

    sock.ev.on('creds.update', saveCreds)

    sock.ev.on('messages.upsert', async ({ messages, type }) => {
        if (type !== 'notify') return

        const msg = messages[0]
        if (!msg.message || msg.key.fromMe) return

        // Skip pesan dari grup (opsional, hapus baris ini kalau mau aktif di grup)
        // if (msg.key.remoteJid.endsWith('@g.us')) return

        const text = msg.message.conversation ||
                     msg.message.extendedTextMessage?.text || ''
        const from = msg.key.remoteJid

        if (!text || text.trim() === '') return

        console.log(`📨 [${from}]: ${text}`)

        try {
            // Cek apakah command
            const commandReply = await handleCommand(sock, from, text)
            if (commandReply) {
                await sock.sendMessage(from, { text: commandReply })
                return
            }

            // Bukan command, proses sebagai AI chat
            await sock.sendPresenceUpdate('composing', from)

            const session = getSession(from)
            addToHistory(from, 'user', text)

            const useSearch = session.mode === 'search'
            const reply = await askAI(text, useSearch)

            addToHistory(from, 'assistant', reply)
            await sock.sendMessage(from, { text: reply })
            console.log(`🤖 [BOT → ${from}]: ${reply.substring(0, 80)}...`)

        } catch (e) {
            console.error('Error handling message:', e)
            await sock.sendMessage(from, { text: '❌ Terjadi kesalahan. Coba lagi.' })
        }
    })
}

console.log('🚀 Starting Claw AI WhatsApp Bot...')
startBot()
