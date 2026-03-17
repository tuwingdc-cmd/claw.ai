"""
Text-to-Speech via Edge TTS (Free, No API Key)
Microsoft Neural Voices - 300+ voices, 50+ languages
"""

import os
import re
import uuid
import logging
import time

log = logging.getLogger(__name__)

TTS_DIR = "/tmp/tts"
os.makedirs(TTS_DIR, exist_ok=True)

# ============================================================
# VOICE PRESETS
# ============================================================

VOICES = {
    "id-female": "id-ID-GadisNeural",
    "id-male": "id-ID-ArdiNeural",
    "en-female": "en-US-JennyNeural",
    "en-male": "en-US-GuyNeural",
    "en-uk-female": "en-GB-SoniaNeural",
    "en-uk-male": "en-GB-RyanNeural",
    "ja-female": "ja-JP-NanamiNeural",
    "ja-male": "ja-JP-KeitaNeural",
    "ko-female": "ko-KR-SunHiNeural",
    "ko-male": "ko-KR-InJoonNeural",
    "zh-female": "zh-CN-XiaoxiaoNeural",
    "zh-male": "zh-CN-YunxiNeural",
    "es-female": "es-ES-ElviraNeural",
    "es-male": "es-ES-AlvaroNeural",
    "fr-female": "fr-FR-DeniseNeural",
    "fr-male": "fr-FR-HenriNeural",
    "de-female": "de-DE-KatjaNeural",
    "de-male": "de-DE-ConradNeural",
    "ar-female": "ar-SA-ZariyahNeural",
    "ar-male": "ar-SA-HamedNeural",
}

VOICE_ALIASES = {
    "gadis": "id-ID-GadisNeural",
    "ardi": "id-ID-ArdiNeural",
    "jenny": "en-US-JennyNeural",
    "guy": "en-US-GuyNeural",
    "nanami": "ja-JP-NanamiNeural",
    "sonia": "en-GB-SoniaNeural",
    "keita": "ja-JP-KeitaNeural",
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",
}

SPEED_PRESETS = {
    "sangat-lambat": "-50%",
    "lambat": "-25%",
    "slow": "-25%",
    "normal": "+0%",
    "cepat": "+25%",
    "fast": "+25%",
    "sangat-cepat": "+50%",
    "fastest": "+50%",
    "turbo": "+80%",
}


def parse_speed(value: str) -> str:
    """Parse speed input to edge-tts format"""
    if not value:
        return "+0%"

    value = value.lower().strip()

    # Check presets
    if value in SPEED_PRESETS:
        return SPEED_PRESETS[value]

    # Already in format like +20% or -10%
    if re.match(r'^[+-]?\d+%$', value):
        if not value.startswith(('+', '-')):
            value = f"+{value}"
        return value

    # Number like 1.5, 2, 0.8
    try:
        num = float(value.replace('x', '').replace('X', ''))
        percent = int((num - 1.0) * 100)
        sign = "+" if percent >= 0 else ""
        return f"{sign}{percent}%"
    except ValueError:
        pass

    return "+0%"


# ============================================================
# LANGUAGE DETECTION
# ============================================================

def detect_language(text: str) -> str:
    """Simple language detection"""
    # Japanese
    if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text):
        return "ja"
    # Korean
    if re.search(r'[\uac00-\ud7af]', text):
        return "ko"
    # Chinese (CJK without Japanese kana)
    if re.search(r'[\u4e00-\u9fff]', text) and not re.search(r'[\u3040-\u30ff]', text):
        return "zh"
    # Arabic
    if re.search(r'[\u0600-\u06ff]', text):
        return "ar"

    # Indonesian detection
    indo_words = {
        "saya", "aku", "kamu", "dia", "kami", "mereka", "ini", "itu",
        "dan", "atau", "yang", "di", "ke", "dari", "untuk", "dengan",
        "tidak", "bukan", "sudah", "belum", "akan", "bisa", "harus",
        "ada", "mau", "lagi", "juga", "seperti", "karena", "tapi",
        "adalah", "dalam", "pada", "oleh", "sebuah", "satu",
        "pagi", "siang", "sore", "malam", "hari", "waktu",
        "tolong", "silakan", "terima", "kasih", "mohon",
        "bagaimana", "mengapa", "dimana", "kapan", "siapa",
        "gimana", "kenapa", "gak", "nggak", "dong", "sih", "nih",
    }
    words = text.lower().split()
    if words:
        indo_count = sum(1 for w in words if w.strip(".,!?\"'()") in indo_words)
        if indo_count / len(words) > 0.15:
            return "id"

    return "en"


def get_voice_id(lang: str = None, gender: str = "female", voice_name: str = None) -> str:
    """Get voice ID"""
    if voice_name:
        if voice_name.lower() in VOICE_ALIASES:
            return VOICE_ALIASES[voice_name.lower()]
        if "Neural" in voice_name:
            return voice_name
        if voice_name.lower() in VOICES:
            return VOICES[voice_name.lower()]

    lang = lang or "id"
    gender = gender or "female"
    key = f"{lang}-{gender}"
    return VOICES.get(key, VOICES.get(f"{lang}-female", "id-ID-GadisNeural"))


# ============================================================
# TTS GENERATION
# ============================================================

def clean_text_for_tts(text: str) -> str:
    """Clean text for better TTS output"""
    # Remove markdown
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'```[\s\S]*?```', '', text)

    # Remove Discord formatting
    text = re.sub(r'-#\s.*', '', text)  # subtext
    text = re.sub(r'https?://\S+', '', text)  # URLs
    text = re.sub(r'<@!?\d+>', '', text)  # mentions
    text = re.sub(r'<#\d+>', '', text)  # channel mentions
    text = re.sub(r'<a?:\w+:\d+>', '', text)  # emoji

    # Remove excess whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()


async def generate_tts(
    text: str,
    voice: str = None,
    lang: str = None,
    gender: str = "female",
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> dict:
    """Generate TTS audio file"""
    try:
        import edge_tts
    except ImportError:
        return {"success": False, "error": "edge-tts not installed"}

    # Clean and validate
    text = clean_text_for_tts(text)
    if not text:
        return {"success": False, "error": "Text is empty after cleaning"}

    if len(text) > 3000:
        text = text[:3000]

    # Auto-detect language
    if not lang:
        lang = detect_language(text)

    voice_id = get_voice_id(lang=lang, gender=gender, voice_name=voice)

    # Generate file
    file_id = uuid.uuid4().hex[:12]
    filename = f"{file_id}.mp3"
    filepath = os.path.join(TTS_DIR, filename)

    try:
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice_id,
            rate=rate,
            pitch=pitch,
        )
        await communicate.save(filepath)

        if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
            log.info(f"🔊 TTS: {voice_id} | {len(text)} chars | speed={rate}")
            return {
                "success": True,
                "filepath": filepath,
                "filename": filename,
                "voice": voice_id,
                "lang": lang,
                "text_length": len(text),
            }
        return {"success": False, "error": "Output file empty"}

    except Exception as e:
        log.error(f"🔊 TTS error: {e}")
        return {"success": False, "error": str(e)}


def cleanup_old_tts(max_age_seconds: int = 120):
    """Remove old TTS files"""
    try:
        now = time.time()
        for f in os.listdir(TTS_DIR):
            fp = os.path.join(TTS_DIR, f)
            if now - os.path.getmtime(fp) > max_age_seconds:
                os.unlink(fp)
    except Exception as e:
        log.warning(f"TTS cleanup error: {e}")
