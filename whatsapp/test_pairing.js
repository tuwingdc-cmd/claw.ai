const { makeWASocket, useMultiFileAuthState } = require('baileys')
const pino = require('pino')
const readline = require('readline')

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
})

async function connect() {
    console.log('Preparing...')
    
    const { state, saveCreds } = await useMultiFileAuthState('./auth_test')
    
    const sock = makeWASocket({
        auth: state,
        logger: pino({ level: 'silent' }),
        browser: ['Chrome', 'Chrome', '125.0.0'],
    })

    sock.ev.on('creds.update', saveCreds)
    
    sock.ev.on('connection.update', async (update) => {
        const { connection, qr } = update
        
        if (qr && !sock.authState.creds.registered) {
            rl.question('Nomor WA (62xxx): ', async (phone) => {
                try {
                    const code = await sock.requestPairingCode(phone)
                    console.log(`\n🔢 CODE: ${code}`)
                    console.log('WA > Linked Devices > Link with phone number')
                } catch(e) {
                    console.log('Retry...')
                }
            })
        }
        
        if (connection === 'open') {
            console.log('\n✅ CONNECTED!')
            console.log('Copy auth_test ke server!')
        }
    })
}

connect()
