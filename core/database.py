"""
Persistent Storage - Settings + Conversation Memory
"""

import sqlite3
import json
import logging
import os
from typing import Optional, Dict, List
from datetime import datetime

log = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bot.db")

DEFAULT_SETTINGS = {
    "profiles": {
        "normal": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "reasoning": {"provider": "groq", "model": "deepseek-r1-distill-llama-70b"},
        "search": {"provider": "groq", "model": "llama-3.3-70b-versatile", "engine": "duckduckgo"},
    },
    "active_mode": "normal",
    "auto_chat": False,
    "auto_detect": False,
    "enabled_channels": [],
}

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            settings TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            user_name TEXT DEFAULT '',
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_conv_channel 
        ON conversations(guild_id, channel_id, created_at)
    """)
    
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_conv_user 
        ON conversations(user_id, created_at)
    """)
    
    conn.commit()
    conn.close()
    log.info(f"Database initialized: {DB_PATH}")

# ============================================================
# SETTINGS CRUD
# ============================================================

def load_settings(guild_id: int) -> dict:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT settings FROM guild_settings WHERE guild_id = ?", (guild_id,))
        row = c.fetchone()
        conn.close()
        if row:
            saved = json.loads(row[0])
            merged = json.loads(json.dumps(DEFAULT_SETTINGS))
            _deep_merge(merged, saved)
            return merged
        return json.loads(json.dumps(DEFAULT_SETTINGS))
    except Exception as e:
        log.error(f"Error loading settings: {e}")
        return json.loads(json.dumps(DEFAULT_SETTINGS))

def save_settings(guild_id: int, settings: dict):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO guild_settings (guild_id, settings, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(guild_id) DO UPDATE SET
                settings = excluded.settings, updated_at = CURRENT_TIMESTAMP
        """, (guild_id, json.dumps(settings)))
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"Error saving settings: {e}")

def delete_settings(guild_id: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM guild_settings WHERE guild_id = ?", (guild_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"Error deleting settings: {e}")

def _deep_merge(base: dict, override: dict):
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value

# ============================================================
# CONVERSATION MEMORY (Database-backed)
# ============================================================

MAX_MEMORY_MESSAGES = 50  # Per channel, diperbesar!

def save_message(guild_id: int, channel_id: int, user_id: int, user_name: str, role: str, content: str):
    """Save a message to conversation history"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO conversations (guild_id, channel_id, user_id, user_name, role, content)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (guild_id, channel_id, user_id, user_name, role, content[:2000]))
        
        # Cleanup old messages beyond limit per channel
        c.execute("""
            DELETE FROM conversations WHERE id NOT IN (
                SELECT id FROM conversations 
                WHERE guild_id = ? AND channel_id = ?
                ORDER BY created_at DESC LIMIT ?
            ) AND guild_id = ? AND channel_id = ?
        """, (guild_id, channel_id, MAX_MEMORY_MESSAGES, guild_id, channel_id))
        
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"Error saving message: {e}")

def get_conversation(guild_id: int, channel_id: int, limit: int = 30) -> List[Dict]:
    """Get conversation history for a channel"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT role, content, user_name, user_id FROM conversations
            WHERE guild_id = ? AND channel_id = ?
            ORDER BY created_at DESC LIMIT ?
        """, (guild_id, channel_id, limit))
        rows = c.fetchall()
        conn.close()
        
        # Reverse to get chronological order
        messages = []
        for role, content, user_name, user_id in reversed(rows):
            msg = {"role": role, "content": content}
            if role == "user" and user_name:
                msg["user_name"] = user_name
                msg["user_id"] = user_id
            messages.append(msg)
        return messages
    except Exception as e:
        log.error(f"Error getting conversation: {e}")
        return []

def get_user_history(user_id: int, limit: int = 20) -> List[Dict]:
    """Get conversation history for a specific user (across channels)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT role, content, channel_id FROM conversations
            WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit))
        rows = c.fetchall()
        conn.close()
        return [{"role": r, "content": c, "channel_id": ch} for r, c, ch in reversed(rows)]
    except Exception as e:
        log.error(f"Error getting user history: {e}")
        return []

def clear_conversation(guild_id: int, channel_id: int = None):
    """Clear conversation history"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        if channel_id:
            c.execute("DELETE FROM conversations WHERE guild_id = ? AND channel_id = ?", (guild_id, channel_id))
        else:
            c.execute("DELETE FROM conversations WHERE guild_id = ?", (guild_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"Error clearing conversation: {e}")

def get_memory_stats(guild_id: int) -> dict:
    """Get memory statistics"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(DISTINCT channel_id), COUNT(*) FROM conversations WHERE guild_id = ?", (guild_id,))
        channels, total = c.fetchone()
        c.execute("SELECT COUNT(DISTINCT user_id) FROM conversations WHERE guild_id = ?", (guild_id,))
        users = c.fetchone()[0]
        conn.close()
        return {"channels": channels, "total_messages": total, "users": users}
    except:
        return {"channels": 0, "total_messages": 0, "users": 0}

# ============================================================
# SETTINGS MANAGER (Cache + Auto-save)
# ============================================================

class SettingsManager:
    _cache: Dict[int, dict] = {}
    
    @classmethod
    def get(cls, guild_id: int) -> dict:
        if guild_id not in cls._cache:
            cls._cache[guild_id] = load_settings(guild_id)
        return cls._cache[guild_id]
    
    @classmethod
    def save(cls, guild_id: int):
        if guild_id in cls._cache:
            save_settings(guild_id, cls._cache[guild_id])
    
    @classmethod
    def reset(cls, guild_id: int):
        cls._cache[guild_id] = json.loads(json.dumps(DEFAULT_SETTINGS))
        save_settings(guild_id, cls._cache[guild_id])
    
    @classmethod
    def get_all_guilds(cls) -> list:
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT guild_id FROM guild_settings")
            rows = c.fetchall()
            conn.close()
            return [r[0] for r in rows]
        except:
            return []

# ============================================================
# REMINDER SYSTEM - Persistent Scheduled Reminders
# ============================================================

def init_reminders_table():
    """Create reminders table if not exists"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            user_name TEXT,
            message TEXT NOT NULL,
            trigger_type TEXT DEFAULT 'once',
            trigger_time TEXT,
            trigger_minutes INTEGER,
            cron_expression TEXT,
            timezone TEXT DEFAULT 'Asia/Jakarta',
            actions TEXT,
            is_active INTEGER DEFAULT 1,
            last_triggered TEXT,
            next_trigger TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_reminder_active ON reminders(is_active, next_trigger)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_reminder_user ON reminders(guild_id, user_id)')
    conn.commit()
    conn.close()
    log.info("Reminders table initialized")

def create_reminder(guild_id: int, channel_id: int, user_id: int, user_name: str,
                    message: str, trigger_type: str, trigger_time: str = None,
                    trigger_minutes: int = None, cron_expression: str = None,
                    timezone: str = "Asia/Jakarta", actions: list = None,
                    target_user_id: int = None, target_user_name: str = None) -> int:
    """Create new reminder, return ID"""
    import pytz
    from datetime import timedelta
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Calculate next_trigger
    try:
        tz = pytz.timezone(timezone)
    except:
        tz = pytz.timezone("Asia/Jakarta")
    
    now = datetime.now(tz)
    
    if trigger_type == "minutes" and trigger_minutes:
        next_trigger = now + timedelta(minutes=trigger_minutes)
    elif trigger_type == "once" and trigger_time:
        if " " in str(trigger_time):
            next_trigger = datetime.strptime(trigger_time, "%Y-%m-%d %H:%M")
            next_trigger = tz.localize(next_trigger)
        else:
            hour, minute = map(int, str(trigger_time).split(":"))
            next_trigger = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_trigger <= now:
                next_trigger += timedelta(days=1)
    elif trigger_type == "daily" and trigger_time:
        hour, minute = map(int, str(trigger_time).split(":"))
        next_trigger = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_trigger <= now:
            next_trigger += timedelta(days=1)
    elif trigger_type == "weekly" and trigger_time:
        hour, minute = map(int, str(trigger_time).split(":"))
        next_trigger = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_trigger <= now:
            next_trigger += timedelta(weeks=1)
    else:
        next_trigger = now + timedelta(minutes=5)
    
    c.execute('''
        INSERT INTO reminders 
        (guild_id, channel_id, user_id, user_name, message, trigger_type,
         trigger_time, trigger_minutes, cron_expression, timezone, actions, next_trigger,
         target_user_id, target_user_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        guild_id, channel_id, user_id, user_name, message, trigger_type,
        trigger_time, trigger_minutes, cron_expression, timezone,
        json.dumps(actions or []), next_trigger.isoformat(),
        target_user_id, target_user_name
    ))
    
    reminder_id = c.lastrowid
    conn.commit()
    conn.close()
    
    log.info(f"⏰ Reminder #{reminder_id} created: {message} -> {next_trigger}")
    return reminder_id

def get_due_reminders() -> list:
    """Get all reminders that should trigger now"""
    import pytz
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM reminders WHERE is_active = 1 AND next_trigger IS NOT NULL')
    rows = c.fetchall()
    columns = [desc[0] for desc in c.description]
    conn.close()
    
    due = []
    now_utc = datetime.now(pytz.UTC)
    
    for row in rows:
        reminder = dict(zip(columns, row))
        try:
            tz = pytz.timezone(reminder.get("timezone", "Asia/Jakarta"))
            next_trigger = datetime.fromisoformat(reminder["next_trigger"])
            if next_trigger.tzinfo is None:
                next_trigger = tz.localize(next_trigger)
            next_trigger_utc = next_trigger.astimezone(pytz.UTC)
            
            if next_trigger_utc <= now_utc:
                reminder["actions"] = json.loads(reminder.get("actions", "[]") or "[]")
                due.append(reminder)
        except Exception as e:
            log.warning(f"Error parsing reminder {reminder.get('id')}: {e}")
    
    return due

def mark_reminder_triggered(reminder_id: int, reschedule: bool = False):
    """Mark reminder as triggered, optionally reschedule for recurring"""
    import pytz
    from datetime import timedelta
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now(pytz.UTC).isoformat()
    
    if reschedule:
        c.execute('SELECT * FROM reminders WHERE id = ?', (reminder_id,))
        row = c.fetchone()
        if row:
            columns = [desc[0] for desc in c.description]
            reminder = dict(zip(columns, row))
            
            try:
                tz = pytz.timezone(reminder.get("timezone", "Asia/Jakarta"))
            except:
                tz = pytz.timezone("Asia/Jakarta")
            
            now_local = datetime.now(tz)
            
            if reminder["trigger_type"] == "daily" and reminder.get("trigger_time"):
                hour, minute = map(int, str(reminder["trigger_time"]).split(":"))
                next_trigger = now_local.replace(hour=hour, minute=minute, second=0)
                next_trigger += timedelta(days=1)
                c.execute('UPDATE reminders SET last_triggered = ?, next_trigger = ? WHERE id = ?',
                         (now, next_trigger.isoformat(), reminder_id))
            elif reminder["trigger_type"] == "weekly":
                next_trigger = datetime.fromisoformat(reminder["next_trigger"])
                if next_trigger.tzinfo is None:
                    next_trigger = tz.localize(next_trigger)
                next_trigger += timedelta(weeks=1)
                c.execute('UPDATE reminders SET last_triggered = ?, next_trigger = ? WHERE id = ?',
                         (now, next_trigger.isoformat(), reminder_id))
            else:
                c.execute('UPDATE reminders SET is_active = 0, last_triggered = ? WHERE id = ?',
                         (now, reminder_id))
    else:
        c.execute('UPDATE reminders SET is_active = 0, last_triggered = ? WHERE id = ?',
                 (now, reminder_id))
    
    conn.commit()
    conn.close()

def get_user_reminders(guild_id: int, user_id: int) -> list:
    """Get all active reminders for a user"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT * FROM reminders 
        WHERE guild_id = ? AND user_id = ? AND is_active = 1
        ORDER BY next_trigger ASC
    ''', (guild_id, user_id))
    rows = c.fetchall()
    columns = [desc[0] for desc in c.description]
    conn.close()
    
    reminders = []
    for row in rows:
        r = dict(zip(columns, row))
        r["actions"] = json.loads(r.get("actions", "[]") or "[]")
        reminders.append(r)
    return reminders

def get_all_active_reminders(guild_id: int = None) -> list:
    """Get all active reminders (optionally filtered by guild)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if guild_id:
        c.execute('SELECT * FROM reminders WHERE guild_id = ? AND is_active = 1 ORDER BY next_trigger', (guild_id,))
    else:
        c.execute('SELECT * FROM reminders WHERE is_active = 1 ORDER BY next_trigger')
    rows = c.fetchall()
    columns = [desc[0] for desc in c.description]
    conn.close()
    
    reminders = []
    for row in rows:
        r = dict(zip(columns, row))
        r["actions"] = json.loads(r.get("actions", "[]") or "[]")
        reminders.append(r)
    return reminders

def delete_reminder(reminder_id: int, user_id: int = None) -> bool:
    """Delete a reminder (optionally verify owner)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if user_id:
        c.execute('DELETE FROM reminders WHERE id = ? AND user_id = ?', (reminder_id, user_id))
    else:
        c.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    if deleted:
        log.info(f"⏰ Reminder #{reminder_id} deleted")
    return deleted

def cancel_reminder_by_message(guild_id: int, user_id: int, keyword: str) -> int:
    """Cancel reminders matching keyword in message"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE reminders SET is_active = 0 
        WHERE guild_id = ? AND user_id = ? AND is_active = 1 AND message LIKE ?
    ''', (guild_id, user_id, f"%{keyword}%"))
    count = c.rowcount
    conn.commit()
    conn.close()
    return count
