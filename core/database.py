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
