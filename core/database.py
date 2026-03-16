"""
Persistent Storage - Settings + Conversation Memory
Local SQLite (dev) ←→ Turso Cloud (production) via HTTP API
"""

import json
import logging
import os
import sqlite3
from typing import Dict, List
from datetime import datetime

log = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bot.db")

TURSO_URL = os.getenv("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")
USE_TURSO = bool(TURSO_URL and TURSO_TOKEN)


# ============================================================
# TURSO HTTP API WRAPPER  (drop-in sqlite3 replacement)
# No Rust compiler needed — pure HTTP via httpx
# ============================================================

class TursoCursor:
    def __init__(self, conn):
        self._conn = conn
        self._rows: list = []
        self._description = None
        self._lastrowid = None
        self._rowcount = -1
        self._pos = 0

    @property
    def description(self):
        return self._description

    @property
    def lastrowid(self):
        return self._lastrowid

    @property
    def rowcount(self):
        return self._rowcount

    def execute(self, sql, params=None):
        import httpx

        # Convert Python params → Turso arg format
        args = []
        for p in (params or []):
            if p is None:
                args.append({"type": "null", "value": None})
            elif isinstance(p, bool):
                args.append({"type": "integer", "value": str(int(p))})
            elif isinstance(p, int):
                args.append({"type": "integer", "value": str(p)})
            elif isinstance(p, float):
                args.append({"type": "float", "value": str(p)})
            else:
                args.append({"type": "text", "value": str(p)})

        payload = {
            "requests": [
                {"type": "execute", "stmt": {"sql": sql, "args": args}},
                {"type": "close"}
            ]
        }

        try:
            resp = httpx.post(
                self._conn._api_url,
                json=payload,
                headers=self._conn._headers,
                timeout=30.0
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.error(f"Turso HTTP error: {e}")
            raise

        results = data.get("results", [])
        if not results:
            self._rows = []
            return self

        first = results[0]

        # Check for SQL errors from Turso
        if first.get("type") == "error":
            err = first.get("error", {}).get("message", "Unknown Turso error")
            raise Exception(f"Turso SQL error: {err}")

        result = first.get("response", {}).get("result", {})

        # Parse column descriptions
        cols = result.get("cols", [])
        if cols:
            self._description = [(c["name"],) + (None,) * 6 for c in cols]
        else:
            self._description = None

        # Parse rows
        self._rows = []
        for row in result.get("rows", []):
            parsed = []
            for cell in row:
                ct = cell.get("type", "null")
                cv = cell.get("value")
                if ct == "null" or cv is None:
                    parsed.append(None)
                elif ct == "integer":
                    parsed.append(int(cv))
                elif ct == "float":
                    parsed.append(float(cv))
                else:
                    parsed.append(str(cv))
            self._rows.append(tuple(parsed))

        # Metadata
        lir = result.get("last_insert_rowid")
        self._lastrowid = int(lir) if lir is not None else None
        arc = result.get("affected_row_count")
        self._rowcount = int(arc) if arc is not None else -1
        self._pos = 0

        return self

    def fetchone(self):
        if self._pos < len(self._rows):
            row = self._rows[self._pos]
            self._pos += 1
            return row
        return None

    def fetchall(self):
        rows = self._rows[self._pos:]
        self._pos = len(self._rows)
        return rows


class TursoConnection:
    def __init__(self, url, token):
        clean = url.replace("libsql://", "").replace("https://", "").replace("http://", "").rstrip("/")
        self._api_url = f"https://{clean}/v2/pipeline"
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def cursor(self):
        return TursoCursor(self)

    def commit(self):
        pass  # Turso auto-commits each statement

    def close(self):
        pass  # Stateless HTTP — nothing to close


# ============================================================
# CONNECTION FACTORY
# ============================================================

def _get_conn():
    """Returns TursoConnection (cloud) or sqlite3.Connection (local)"""
    if USE_TURSO:
        return TursoConnection(TURSO_URL, TURSO_TOKEN)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


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
    conn = _get_conn()
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

    storage = "Turso Cloud" if USE_TURSO else f"Local SQLite ({DB_PATH})"
    log.info(f"Database initialized: {storage}")


# ============================================================
# SETTINGS CRUD
# ============================================================

def load_settings(guild_id: int) -> dict:
    try:
        conn = _get_conn()
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
        conn = _get_conn()
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
        conn = _get_conn()
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
# CONVERSATION MEMORY
# ============================================================

MAX_MEMORY_MESSAGES = 50


def save_message(guild_id: int, channel_id: int, user_id: int, user_name: str, role: str, content: str):
    try:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO conversations (guild_id, channel_id, user_id, user_name, role, content)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (guild_id, channel_id, user_id, user_name, role, content[:2000]))

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
    try:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT role, content, user_name, user_id FROM conversations
            WHERE guild_id = ? AND channel_id = ?
            ORDER BY created_at DESC LIMIT ?
        """, (guild_id, channel_id, limit))
        rows = c.fetchall()
        conn.close()

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
    try:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT role, content, channel_id FROM conversations
            WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit))
        rows = c.fetchall()
        conn.close()
        return [{"role": r, "content": ct, "channel_id": ch} for r, ct, ch in reversed(rows)]
    except Exception as e:
        log.error(f"Error getting user history: {e}")
        return []


def clear_conversation(guild_id: int, channel_id: int = None):
    try:
        conn = _get_conn()
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
    try:
        conn = _get_conn()
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
            conn = _get_conn()
            c = conn.cursor()
            c.execute("SELECT guild_id FROM guild_settings")
            rows = c.fetchall()
            conn.close()
            return [r[0] for r in rows]
        except:
            return []


# ============================================================
# REMINDER SYSTEM
# ============================================================

def init_reminders_table():
    conn = _get_conn()
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
            target_user_id INTEGER,
            target_user_name TEXT,
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
    import pytz
    from datetime import timedelta

    conn = _get_conn()
    c = conn.cursor()

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
         trigger_time, trigger_minutes, cron_expression, timezone, actions,
         next_trigger, target_user_id, target_user_name)
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

    log.info(f"Reminder #{reminder_id} created: {message} -> {next_trigger}")
    return reminder_id


def get_due_reminders() -> list:
    import pytz

    conn = _get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM reminders WHERE is_active = 1 AND next_trigger IS NOT NULL')
    rows = c.fetchall()
    columns = [desc[0] for desc in c.description] if c.description else []
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
            if next_trigger.astimezone(pytz.UTC) <= now_utc:
                reminder["actions"] = json.loads(reminder.get("actions", "[]") or "[]")
                due.append(reminder)
        except Exception as e:
            log.warning(f"Error parsing reminder {reminder.get('id')}: {e}")

    return due


def mark_reminder_triggered(reminder_id: int, reschedule: bool = False):
    import pytz
    from datetime import timedelta

    conn = _get_conn()
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
                next_t = now_local.replace(hour=hour, minute=minute, second=0) + timedelta(days=1)
                c.execute('UPDATE reminders SET last_triggered=?, next_trigger=? WHERE id=?',
                         (now, next_t.isoformat(), reminder_id))
            elif reminder["trigger_type"] == "weekly":
                next_t = datetime.fromisoformat(reminder["next_trigger"])
                if next_t.tzinfo is None:
                    next_t = tz.localize(next_t)
                next_t += timedelta(weeks=1)
                c.execute('UPDATE reminders SET last_triggered=?, next_trigger=? WHERE id=?',
                         (now, next_t.isoformat(), reminder_id))
            else:
                c.execute('UPDATE reminders SET is_active=0, last_triggered=? WHERE id=?',
                         (now, reminder_id))
    else:
        c.execute('UPDATE reminders SET is_active=0, last_triggered=? WHERE id=?',
                 (now, reminder_id))

    conn.commit()
    conn.close()


def get_user_reminders(guild_id: int, user_id: int) -> list:
    conn = _get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM reminders WHERE guild_id=? AND user_id=? AND is_active=1 ORDER BY next_trigger',
              (guild_id, user_id))
    rows = c.fetchall()
    columns = [desc[0] for desc in c.description] if c.description else []
    conn.close()
    reminders = []
    for row in rows:
        r = dict(zip(columns, row))
        r["actions"] = json.loads(r.get("actions", "[]") or "[]")
        reminders.append(r)
    return reminders


def get_all_active_reminders(guild_id: int = None) -> list:
    conn = _get_conn()
    c = conn.cursor()
    if guild_id:
        c.execute('SELECT * FROM reminders WHERE guild_id=? AND is_active=1 ORDER BY next_trigger', (guild_id,))
    else:
        c.execute('SELECT * FROM reminders WHERE is_active=1 ORDER BY next_trigger')
    rows = c.fetchall()
    columns = [desc[0] for desc in c.description] if c.description else []
    conn.close()
    reminders = []
    for row in rows:
        r = dict(zip(columns, row))
        r["actions"] = json.loads(r.get("actions", "[]") or "[]")
        reminders.append(r)
    return reminders


def delete_reminder(reminder_id: int, user_id: int = None) -> bool:
    conn = _get_conn()
    c = conn.cursor()
    if user_id:
        c.execute('DELETE FROM reminders WHERE id=? AND user_id=?', (reminder_id, user_id))
    else:
        c.execute('DELETE FROM reminders WHERE id=?', (reminder_id,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    if deleted:
        log.info(f"Reminder #{reminder_id} deleted")
    return deleted


def cancel_reminder_by_message(guild_id: int, user_id: int, keyword: str) -> int:
    conn = _get_conn()
    c = conn.cursor()
    c.execute('''
        UPDATE reminders SET is_active=0
        WHERE guild_id=? AND user_id=? AND is_active=1 AND message LIKE ?
    ''', (guild_id, user_id, f"%{keyword}%"))
    count = c.rowcount
    conn.commit()
    conn.close()
    return count
