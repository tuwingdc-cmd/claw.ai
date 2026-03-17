from flask import Flask, send_from_directory
import threading
import asyncio
import aiohttp
import os
import logging

log = logging.getLogger(__name__)

app = Flask(__name__)

PORT = int(os.getenv("PORT", 3007))
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "")
TTS_DIR = "/tmp/tts"


@app.route("/")
def home():
    return "Bot is running!", 200


@app.route("/health")
def health():
    return "OK", 200


@app.route("/tts/<filename>")
def serve_tts(filename):
    """Serve TTS audio files for Lavalink"""
    if not filename.endswith(".mp3"):
        return "Not found", 404
    try:
        return send_from_directory(TTS_DIR, filename, mimetype="audio/mpeg")
    except FileNotFoundError:
        return "Not found", 404


def keep_alive():
    log.info(f"🌐 Web server starting on port {PORT}")

    def run():
        app.run(host="0.0.0.0", port=PORT)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    log.info("🌐 Keep-alive web server started!")


async def self_ping():
    url = RENDER_URL or os.getenv("RENDER_EXTERNAL_URL", "")
    if not url:
        log.warning("🏓 RENDER_EXTERNAL_URL not set, self-ping disabled")
        return

    health_url = f"{url}/health"
    await asyncio.sleep(30)
    log.info(f"🏓 Self-ping enabled: {health_url} (every 5 min)")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(health_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    log.info(f"🏓 Self-ping: {resp.status}")
            except Exception as e:
                log.warning(f"🏓 Self-ping error: {e}")
            await asyncio.sleep(300)
