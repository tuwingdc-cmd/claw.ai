const sqlite3 = require('sqlite3').verbose()
const path = require('path')

const DB_PATH = path.join(__dirname, 'session', 'chat_history.db')

// Initialize database
const db = new sqlite3.Database(DB_PATH, (err) => {
    if (err) console.error('Database error:', err)
    else console.log('💾 Database connected:', DB_PATH)
})

// Create tables
db.serialize(() => {
    db.run(`
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp INTEGER DEFAULT (strftime('%s', 'now'))
        )
    `)
    
    db.run(`
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT PRIMARY KEY,
            provider TEXT DEFAULT 'groq',
            model TEXT DEFAULT 'llama-3.3-70b-versatile',
            mode TEXT DEFAULT 'normal',
            updated_at INTEGER DEFAULT (strftime('%s', 'now'))
        )
    `)
})

// Get conversation history
function getHistory(userId, limit = 10) {
    return new Promise((resolve, reject) => {
        db.all(
            `SELECT role, content FROM conversations 
             WHERE user_id = ? 
             ORDER BY timestamp DESC 
             LIMIT ?`,
            [userId, limit],
            (err, rows) => {
                if (err) reject(err)
                else resolve(rows.reverse()) // Reverse untuk urutan chronological
            }
        )
    })
}

// Add message to history
function addMessage(userId, role, content) {
    return new Promise((resolve, reject) => {
        db.run(
            `INSERT INTO conversations (user_id, role, content) VALUES (?, ?, ?)`,
            [userId, role, content],
            (err) => {
                if (err) reject(err)
                else resolve()
            }
        )
    })
}

// Clear history for user
function clearHistory(userId) {
    return new Promise((resolve, reject) => {
        db.run(
            `DELETE FROM conversations WHERE user_id = ?`,
            [userId],
            (err) => {
                if (err) reject(err)
                else resolve()
            }
        )
    })
}

// Get user settings
function getSettings(userId) {
    return new Promise((resolve, reject) => {
        db.get(
            `SELECT provider, model, mode FROM user_settings WHERE user_id = ?`,
            [userId],
            (err, row) => {
                if (err) reject(err)
                else resolve(row || null)
            }
        )
    })
}

// Save user settings
function saveSettings(userId, provider, model, mode) {
    return new Promise((resolve, reject) => {
        db.run(
            `INSERT INTO user_settings (user_id, provider, model, mode, updated_at)
             VALUES (?, ?, ?, ?, strftime('%s', 'now'))
             ON CONFLICT(user_id) DO UPDATE SET
                provider = excluded.provider,
                model = excluded.model,
                mode = excluded.mode,
                updated_at = excluded.updated_at`,
            [userId, provider, model, mode],
            (err) => {
                if (err) reject(err)
                else resolve()
            }
        )
    })
}

// Get stats
function getStats(userId) {
    return new Promise((resolve, reject) => {
        db.get(
            `SELECT COUNT(*) as total FROM conversations WHERE user_id = ?`,
            [userId],
            (err, row) => {
                if (err) reject(err)
                else resolve(row.total || 0)
            }
        )
    })
}

module.exports = {
    getHistory,
    addMessage,
    clearHistory,
    getSettings,
    saveSettings,
    getStats,
    db
}
