const { makeWASocket, useMultiFileAuthState } = require('baileys')
const pino = require('pino')
const qrcode = require('qrcode-terminal')

async function test() {
    console.log('Starting test...')
    
    const { state, saveCreds } = await useMultiFileAuthState('./auth_test')
    console.log('Auth state loaded - waiting for QR...')
    
    const sock = makeWASocket({
        auth: state,
        logger: pino({ level: 'warn' }),
        browser: ['Claw AI', 'Chrome', '1.0.0'],
    })

    sock.ev.on('creds.update', saveCreds)

    sock.ev.on('connection.update', (update) => {
        const { connection, qr } = update
        
        if (qr) {
            console.log('\n📱 SCAN QR CODE INI:\n')
            qrcode.generate(qr, { small: true })
        }
        
        if (connection === 'open') {
            console.log('\n✅ CONNECTED! WhatsApp terhubung!')
        }
        
        if (connection === 'close') {
            console.log('Connection closed:', JSON.stringify(update.lastDisconnect?.error?.output?.payload))
        }
    })
}

test().catch(e => console.error('FATAL:', e))
