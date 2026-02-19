"""Smart Lyrics Fetcher"""
import asyncio, re, logging

log = logging.getLogger(__name__)

def clean_title(title: str) -> str:
    if not title: return ""
    for p in [r'\(Official.*?\)', r'\[.*?\]', r'\|.*$']:
        title = re.sub(p, '', title, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', title).strip()

def clean_artist(artist: str) -> str:
    if not artist: return ""
    return re.sub(r'\s*-\s*Topic$', '', artist, flags=re.IGNORECASE).strip()

def clean_lyrics_text(text: str) -> str:
    if not text: return ""
    lines = [l for l in text.split('\n') if not re.search(r'(Contributor|Embed|Translation)', l, re.I)]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()

def is_full_album_or_mix(title: str, duration_ms: int = 0) -> bool:
    if duration_ms > 20 * 60 * 1000: return True
    return any(re.search(p, title.lower()) for p in [r'full\s*album', r'mix', r'compilation'])

async def fetch_lyrics(title: str, artist: str = None, duration_ms: int = 0, track_encoded: str = None) -> str:
    if is_full_album_or_mix(title, duration_ms):
        return "🎶 **Full Album/Mix**\nGunakan `.lyrics <judul lagu spesifik>`"
    try:
        import syncedlyrics
        q = f"{clean_title(title)} {clean_artist(artist)}" if artist else clean_title(title)
        log.info(f"Searching lyrics: {q}")
        result = await asyncio.get_event_loop().run_in_executor(None, lambda: syncedlyrics.search(q))
        if result:
            result = re.sub(r'\[\d{2}:\d{2}\.\d{2,3}\]\s*', '', result)
            return clean_lyrics_text(result)
    except Exception as e:
        log.error(f"Lyrics error: {e}")
    return None
