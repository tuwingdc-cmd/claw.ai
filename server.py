"""
Web Server for Render Health Check + Self-Ping
Keep Discord bot alive on Render Free Tier
"""

import os
import time
import logging
import aiohttp
import asyncio
from flask import Flask, jsonify
from threading import Thread
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

# ============================================================
# FLASK WEB SERVER
# ============================================================

app = Flask(__name__)

# Track bot stats
bot_stats = {
    "start_time": None,
    "ping_count": 0,
    "last_ping": None,
    "status": "starting"
}

@app.route('/')
def home():
    """Landing page"""
    uptime = ""
    if bot_stats["start_time"]:
        delta = datetime.now() - bot_stats["start_time"]
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime = f"{hours}h {minutes}m {seconds}s"
    
    return jsonify({
        "status": "🤖 Bot is alive!",
        "bot_status": bot_stats["status"],
        "uptime": uptime,
        "ping_count": bot_stats["ping_count"],
        "last_ping": str(bot_stats["last_ping"]) if bot_stats["last_ping"] else None,
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route('/health')
def health():
    """Health check endpoint for UptimeRobot / Cron Job"""
    bot_stats["ping_count"] += 1
    bot_stats["last_ping"] = datetime.now()
    return "OK", 200

@app.route('/stats')
def stats():
    """Detailed stats"""
    uptime_seconds = 0
    if bot_stats["start_time"]:
        uptime_seconds = (datetime.now() - bot_stats["start_time"]).total_seconds()
    
    return jsonify({
        "status": bot_stats["status"],
        "uptime_seconds": int(uptime_seconds),
        "total_pings": bot_stats["ping_count"],
        "last_ping": str(bot_stats["last_ping"]) if bot_stats["last_ping"] else None,
        "started_at": str(bot_stats["start_time"]) if bot_stats["start_time"] else None,
    }), 200

# ============================================================
# RUN FLASK IN BACKGROUND THREAD
# ============================================================

def run_server():
    """Run Flask server (blocking)"""
    port = int(os.environ.get("PORT", 10000))
    bot_stats["start_time"] = datetime.now()
    bot_stats["status"] = "running"
    log.info(f"🌐 Web server starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def keep_alive():
    """Start Flask server in a daemon thread"""
    thread = Thread(target=run_server, daemon=True)
    thread.start()
    log.info("🌐 Keep-alive web server started!")
    return thread

# ============================================================
# SELF-PING (Backup jika tidak pakai UptimeRobot)
# ============================================================

async def self_ping():
    """
    Ping diri sendiri setiap 5 menit supaya Render tidak sleep.
    Ini backup — lebih baik pakai UptimeRobot / cron-job.org
    """
    # Tunggu 30 detik supaya Flask server ready dulu
    await asyncio.sleep(30)
    
    # Coba ambil URL dari environment
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    
    if not render_url:
        # Fallback: pakai service name dari env
        service_name = os.environ.get("RENDER_SERVICE_NAME", "")
        if service_name:
            render_url = f"https://{service_name}.onrender.com"
        else:
            log.warning("⚠️ RENDER_EXTERNAL_URL not set. Self-ping disabled.")
            log.warning("💡 Set RENDER_EXTERNAL_URL di Environment Variables Render")
            log.warning("💡 Contoh: https://claw-ai-bot.onrender.com")
            return
    
    ping_url = f"{render_url}/health"
    log.info(f"🏓 Self-ping enabled: {ping_url} (every 5 min)")
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(ping_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    log.info(f"🏓 Self-ping: {resp.status}")
            except asyncio.TimeoutError:
                log.warning("🏓 Self-ping timeout")
            except Exception as e:
                log.warning(f"🏓 Self-ping failed: {e}")
            
            # Ping setiap 5 menit (300 detik)
            await asyncio.sleep(300)
