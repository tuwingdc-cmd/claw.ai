"""
Persistent Settings Storage using SQLite
Settings tersimpan permanen, tidak hilang saat restart!
"""

import sqlite3
import json
import logging
import os
from typing import Optional, Dict

log = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bot.db")

# ============================================================
# DEFAULT SETTINGS
# ============================================================

DEFAULT_SETTINGS = {
    "profiles": {
        "normal": {
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
        },
        "reasoning": {
            "provider": "groq",
            "model": "deepseek-r1-distill-llama-70b",
        },
        "search": {
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
            "engine": "duckduckgo",
        },
    },
    "active_mode": "normal",
    "auto_chat": False,
    "auto_detect": False,
    "enabled_channels": [],
}

# ============================================================
# DATABASE INIT
# ============================================================

def init_db():
    """Create tables if not exist"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            settings TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS enabled_channels (
            guild_id INTEGER,
            channel_id INTEGER,
            PRIMARY KEY (guild_id, channel_id)
        )
    """)
    
    conn.commit()
    conn.close()
    log.info(f"Database initialized: {DB_PATH}")

# ============================================================
# SETTINGS CRUD
# ============================================================

def load_settings(guild_id: int) -> dict:
    """Load guild settings from SQLite (with defaults fallback)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT settings FROM guild_settings WHERE guild_id = ?", (guild_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            saved = json.loads(row[0])
            # Merge with defaults (in case new keys added)
            merged = json.loads(json.dumps(DEFAULT_SETTINGS))
            _deep_merge(merged, saved)
            return merged
        
        return json.loads(json.dumps(DEFAULT_SETTINGS))
    except Exception as e:
        log.error(f"Error loading settings for guild {guild_id}: {e}")
        return json.loads(json.dumps(DEFAULT_SETTINGS))

def save_settings(guild_id: int, settings: dict):
    """Save guild settings to SQLite"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        settings_json = json.dumps(settings)
        
        cursor.execute("""
            INSERT INTO guild_settings (guild_id, settings, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(guild_id) DO UPDATE SET
                settings = excluded.settings,
                updated_at = CURRENT_TIMESTAMP
        """, (guild_id, settings_json))
        
        conn.commit()
        conn.close()
        log.debug(f"Settings saved for guild {guild_id}")
    except Exception as e:
        log.error(f"Error saving settings for guild {guild_id}: {e}")

def delete_settings(guild_id: int):
    """Delete guild settings (full reset)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM guild_settings WHERE guild_id = ?", (guild_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"Error deleting settings for guild {guild_id}: {e}")

def _deep_merge(base: dict, override: dict):
    """Deep merge override into base"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value

# ============================================================
# SETTINGS MANAGER (cache + auto-save)
# ============================================================

class SettingsManager:
    """
    Cache settings in memory, auto-save to SQLite on change.
    Best of both worlds: fast reads + persistent storage!
    """
    
    _cache: Dict[int, dict] = {}
    
    @classmethod
    def get(cls, guild_id: int) -> dict:
        """Get settings (from cache or DB)"""
        if guild_id not in cls._cache:
            cls._cache[guild_id] = load_settings(guild_id)
        return cls._cache[guild_id]
    
    @classmethod
    def save(cls, guild_id: int):
        """Save current cached settings to DB"""
        if guild_id in cls._cache:
            save_settings(guild_id, cls._cache[guild_id])
    
    @classmethod
    def reset(cls, guild_id: int):
        """Reset to defaults and save"""
        cls._cache[guild_id] = json.loads(json.dumps(DEFAULT_SETTINGS))
        save_settings(guild_id, cls._cache[guild_id])
    
    @classmethod
    def update(cls, guild_id: int, **kwargs):
        """Update specific keys and auto-save"""
        settings = cls.get(guild_id)
        settings.update(kwargs)
        cls.save(guild_id)
    
    @classmethod
    def get_all_guilds(cls) -> list:
        """Get list of all guilds with saved settings"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT guild_id FROM guild_settings")
            rows = cursor.fetchall()
            conn.close()
            return [r[0] for r in rows]
        except:
            return []
