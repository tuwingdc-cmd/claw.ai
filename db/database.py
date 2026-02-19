"""
Database Layer - PostgreSQL + Redis
Handles persistent storage and caching
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

log = logging.getLogger(__name__)

# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class GuildSettings:
    """Settings for a Discord guild"""
    guild_id: int
    provider: str = "groq"
    model: str = "llama-3.3-70b-versatile"
    mode: str = "normal"
    auto_chat: bool = False
    auto_detect: bool = False
    search_engine: str = "duckduckgo"
    enabled_channels: List[int] = None
    
    def __post_init__(self):
        if self.enabled_channels is None:
            self.enabled_channels = []
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "GuildSettings":
        return cls(**data)

@dataclass
class RequestLog:
    """Log entry for AI requests"""
    id: Optional[int] = None
    timestamp: str = ""
    guild_id: int = 0
    user_id: int = 0
    provider: str = ""
    model: str = ""
    mode: str = "normal"
    success: bool = False
    latency: float = 0.0
    tokens_used: int = 0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)

# ============================================================
# REDIS CACHE
# ============================================================

class RedisCache:
    """Redis cache for health status and rate limits"""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis = None
    
    async def connect(self):
        """Connect to Redis"""
        try:
            import redis.asyncio as redis
            self.redis = redis.from_url(self.redis_url, decode_responses=True)
            await self.redis.ping()
            log.info("Redis connected")
            return True
        except Exception as e:
            log.warning(f"Redis connection failed: {e}")
            self.redis = None
            return False
    
    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
    
    # ----- Provider Health -----
    
    async def set_provider_health(self, provider: str, healthy: bool, ttl: int = 60):
        """Set provider health status"""
        if not self.redis:
            return
        try:
            key = f"health:{provider}"
            await self.redis.setex(key, ttl, "1" if healthy else "0")
        except Exception as e:
            log.error(f"Redis set health error: {e}")
    
    async def get_provider_health(self, provider: str) -> Optional[bool]:
        """Get provider health status"""
        if not self.redis:
            return None
        try:
            key = f"health:{provider}"
            value = await self.redis.get(key)
            if value is not None:
                return value == "1"
            return None
        except Exception as e:
            log.error(f"Redis get health error: {e}")
            return None
    
    # ----- Rate Limits -----
    
    async def increment_rate(self, provider: str, window: int = 60) -> int:
        """Increment rate counter, return current count"""
        if not self.redis:
            return 0
        try:
            key = f"rate:{provider}:{int(datetime.now().timestamp()) // window}"
            count = await self.redis.incr(key)
            await self.redis.expire(key, window * 2)
            return count
        except Exception as e:
            log.error(f"Redis rate error: {e}")
            return 0
    
    async def get_rate(self, provider: str, window: int = 60) -> int:
        """Get current rate count"""
        if not self.redis:
            return 0
        try:
            key = f"rate:{provider}:{int(datetime.now().timestamp()) // window}"
            value = await self.redis.get(key)
            return int(value) if value else 0
        except Exception as e:
            log.error(f"Redis get rate error: {e}")
            return 0
    
    # ----- Guild Settings Cache -----
    
    async def cache_guild_settings(self, guild_id: int, settings: Dict, ttl: int = 300):
        """Cache guild settings"""
        if not self.redis:
            return
        try:
            key = f"guild:{guild_id}"
            await self.redis.setex(key, ttl, json.dumps(settings))
        except Exception as e:
            log.error(f"Redis cache settings error: {e}")
    
    async def get_cached_guild_settings(self, guild_id: int) -> Optional[Dict]:
        """Get cached guild settings"""
        if not self.redis:
            return None
        try:
            key = f"guild:{guild_id}"
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            log.error(f"Redis get settings error: {e}")
            return None
    
    async def invalidate_guild_cache(self, guild_id: int):
        """Invalidate guild settings cache"""
        if not self.redis:
            return
        try:
            key = f"guild:{guild_id}"
            await self.redis.delete(key)
        except Exception as e:
            log.error(f"Redis invalidate error: {e}")

# ============================================================
# POSTGRESQL DATABASE
# ============================================================

class PostgresDB:
    """PostgreSQL database for persistent storage"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
    
    async def connect(self):
        """Connect to PostgreSQL"""
        try:
            import asyncpg
            self.pool = await asyncpg.create_pool(self.database_url, min_size=2, max_size=10)
            log.info("PostgreSQL connected")
            await self._create_tables()
            return True
        except Exception as e:
            log.warning(f"PostgreSQL connection failed: {e}")
            self.pool = None
            return False
    
    async def close(self):
        """Close PostgreSQL connection"""
        if self.pool:
            await self.pool.close()
    
    async def _create_tables(self):
        """Create tables if not exist"""
        if not self.pool:
            return
        
        async with self.pool.acquire() as conn:
            # Guild settings table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id BIGINT PRIMARY KEY,
                    provider VARCHAR(50) DEFAULT 'groq',
                    model VARCHAR(200) DEFAULT 'llama-3.3-70b-versatile',
                    mode VARCHAR(20) DEFAULT 'normal',
                    auto_chat BOOLEAN DEFAULT FALSE,
                    auto_detect BOOLEAN DEFAULT FALSE,
                    search_engine VARCHAR(50) DEFAULT 'duckduckgo',
                    enabled_channels BIGINT[] DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Request logs table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS request_logs (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    guild_id BIGINT,
                    user_id BIGINT,
                    provider VARCHAR(50),
                    model VARCHAR(200),
                    mode VARCHAR(20),
                    success BOOLEAN,
                    latency REAL,
                    tokens_used INTEGER DEFAULT 0,
                    error TEXT
                )
            """)
            
            # Create index on logs
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_guild_time 
                ON request_logs (guild_id, timestamp DESC)
            """)
            
            log.info("Database tables ready")
    
    # ----- Guild Settings -----
    
    async def get_guild_settings(self, guild_id: int) -> Optional[GuildSettings]:
        """Get guild settings from database"""
        if not self.pool:
            return None
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM guild_settings WHERE guild_id = $1",
                    guild_id
                )
                
                if row:
                    return GuildSettings(
                        guild_id=row["guild_id"],
                        provider=row["provider"],
                        model=row["model"],
                        mode=row["mode"],
                        auto_chat=row["auto_chat"],
                        auto_detect=row["auto_detect"],
                        search_engine=row["search_engine"],
                        enabled_channels=list(row["enabled_channels"]) if row["enabled_channels"] else []
                    )
                return None
        except Exception as e:
            log.error(f"Get guild settings error: {e}")
            return None
    
    async def save_guild_settings(self, settings: GuildSettings):
        """Save guild settings to database"""
        if not self.pool:
            return False
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO guild_settings 
                    (guild_id, provider, model, mode, auto_chat, auto_detect, search_engine, enabled_channels, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, CURRENT_TIMESTAMP)
                    ON CONFLICT (guild_id) DO UPDATE SET
                        provider = $2,
                        model = $3,
                        mode = $4,
                        auto_chat = $5,
                        auto_detect = $6,
                        search_engine = $7,
                        enabled_channels = $8,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    settings.guild_id,
                    settings.provider,
                    settings.model,
                    settings.mode,
                    settings.auto_chat,
                    settings.auto_detect,
                    settings.search_engine,
                    settings.enabled_channels
                )
                return True
        except Exception as e:
            log.error(f"Save guild settings error: {e}")
            return False
    
    # ----- Request Logs -----
    
    async def log_request(self, log_entry: RequestLog):
        """Log AI request to database"""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO request_logs 
                    (guild_id, user_id, provider, model, mode, success, latency, tokens_used, error)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                    log_entry.guild_id,
                    log_entry.user_id,
                    log_entry.provider,
                    log_entry.model,
                    log_entry.mode,
                    log_entry.success,
                    log_entry.latency,
                    log_entry.tokens_used,
                    log_entry.error
                )
        except Exception as e:
            log.error(f"Log request error: {e}")
    
    async def get_recent_logs(self, guild_id: int, limit: int = 10) -> List[Dict]:
        """Get recent logs for guild"""
        if not self.pool:
            return []
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM request_logs 
                    WHERE guild_id = $1 
                    ORDER BY timestamp DESC 
                    LIMIT $2
                """, guild_id, limit)
                
                logs = []
                for row in rows:
                    logs.append({
                        "id": row["id"],
                        "timestamp": row["timestamp"].strftime("%H:%M:%S"),
                        "provider": row["provider"],
                        "model": row["model"],
                        "mode": row["mode"],
                        "success": row["success"],
                        "latency": row["latency"],
                        "tokens_used": row["tokens_used"],
                        "error": row["error"]
                    })
                return logs
        except Exception as e:
            log.error(f"Get logs error: {e}")
            return []
    
    async def get_stats(self, guild_id: int, hours: int = 24) -> Dict:
        """Get usage statistics for guild"""
        if not self.pool:
            return {}
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
                        AVG(latency) as avg_latency,
                        SUM(tokens_used) as total_tokens
                    FROM request_logs 
                    WHERE guild_id = $1 
                    AND timestamp > NOW() - INTERVAL '%s hours'
                """ % hours, guild_id)
                
                if row:
                    total = row["total"] or 0
                    success = row["success_count"] or 0
                    return {
                        "total_requests": total,
                        "success_rate": (success / total * 100) if total > 0 else 0,
                        "avg_latency": round(row["avg_latency"] or 0, 2),
                        "total_tokens": row["total_tokens"] or 0
                    }
                return {}
        except Exception as e:
            log.error(f"Get stats error: {e}")
            return {}

# ============================================================
# DATABASE MANAGER (Combined)
# ============================================================

class DatabaseManager:
    """Combined database manager for PostgreSQL + Redis"""
    
    def __init__(self, database_url: str, redis_url: str):
        self.postgres = PostgresDB(database_url)
        self.redis = RedisCache(redis_url)
        self._memory_cache: Dict[int, Dict] = {}  # Fallback in-memory cache
    
    async def connect(self):
        """Connect to all databases"""
        pg_ok = await self.postgres.connect()
        redis_ok = await self.redis.connect()
        
        if not pg_ok:
            log.warning("Running without PostgreSQL - using in-memory storage")
        if not redis_ok:
            log.warning("Running without Redis - using in-memory cache")
        
        return pg_ok or redis_ok
    
    async def close(self):
        """Close all connections"""
        await self.postgres.close()
        await self.redis.close()
    
    async def get_guild_settings(self, guild_id: int) -> Dict:
        """Get guild settings with caching"""
        
        # Try Redis cache first
        cached = await self.redis.get_cached_guild_settings(guild_id)
        if cached:
            return cached
        
        # Try PostgreSQL
        settings = await self.postgres.get_guild_settings(guild_id)
        if settings:
            data = settings.to_dict()
            await self.redis.cache_guild_settings(guild_id, data)
            return data
        
        # Try memory cache
        if guild_id in self._memory_cache:
            return self._memory_cache[guild_id]
        
        # Return defaults
        from config import DEFAULTS
        default_settings = {
            "guild_id": guild_id,
            "provider": DEFAULTS["provider"],
            "model": DEFAULTS["model"],
            "mode": DEFAULTS["mode"],
            "auto_chat": DEFAULTS["auto_chat"],
            "auto_detect": DEFAULTS["auto_detect"],
            "search_engine": DEFAULTS["search_engine"],
            "enabled_channels": []
        }
        self._memory_cache[guild_id] = default_settings
        return default_settings
    
    async def save_guild_settings(self, guild_id: int, settings: Dict):
        """Save guild settings"""
        
        # Update memory cache
        self._memory_cache[guild_id] = settings
        
        # Invalidate Redis cache
        await self.redis.invalidate_guild_cache(guild_id)
        
        # Save to PostgreSQL
        gs = GuildSettings.from_dict(settings)
        await self.postgres.save_guild_settings(gs)
        
        # Update Redis cache
        await self.redis.cache_guild_settings(guild_id, settings)
    
    async def log_request(
        self,
        guild_id: int,
        user_id: int,
        provider: str,
        model: str,
        mode: str,
        success: bool,
        latency: float,
        tokens_used: int = 0,
        error: str = None
    ):
        """Log AI request"""
        log_entry = RequestLog(
            guild_id=guild_id,
            user_id=user_id,
            provider=provider,
            model=model,
            mode=mode,
            success=success,
            latency=latency,
            tokens_used=tokens_used,
            error=error
        )
        await self.postgres.log_request(log_entry)
        
        # Update rate counter in Redis
        await self.redis.increment_rate(provider)
    
    async def get_recent_logs(self, guild_id: int, limit: int = 10) -> List[Dict]:
        """Get recent logs"""
        return await self.postgres.get_recent_logs(guild_id, limit)
    
    async def get_stats(self, guild_id: int) -> Dict:
        """Get usage stats"""
        return await self.postgres.get_stats(guild_id)
