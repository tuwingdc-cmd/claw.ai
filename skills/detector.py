"""
Smart Skill Detector - Auto-detect and execute skills from natural language
"""

import re
import datetime
import pytz
from typing import Optional, Dict

from skills.time_skill import get_current_time, get_time_difference
from skills.calendar_skill import get_calendar, days_until
from skills.weather_skill import get_weather

# ============================================================
# TIMEZONE ALIASES
# ============================================================

TZ_ALIASES = {
    "jakarta": "Asia/Jakarta",
    "tokyo": "Asia/Tokyo",
    "london": "Europe/London",
    "new york": "America/New_York",
    "paris": "Europe/Paris",
    "sydney": "Australia/Sydney",
    "dubai": "Asia/Dubai",
    "singapore": "Asia/Singapore",
    "seoul": "Asia/Seoul",
    "beijing": "Asia/Shanghai",
    "bangkok": "Asia/Bangkok",
    "moscow": "Europe/Moscow",
    "berlin": "Europe/Berlin",
    "los angeles": "America/Los_Angeles",
    "chicago": "America/Chicago",
    "india": "Asia/Kolkata",
    "mumbai": "Asia/Kolkata",
    "wib": "Asia/Jakarta",
    "wita": "Asia/Makassar",
    "wit": "Asia/Jayapura",
    "jst": "Asia/Tokyo",
    "gmt": "GMT",
    "utc": "UTC",
    "est": "America/New_York",
    "pst": "America/Los_Angeles",
    "cst": "America/Chicago",
}

# ============================================================
# MONTH NAMES
# ============================================================

MONTH_NAMES = {
    "januari": 1, "january": 1, "jan": 1,
    "februari": 2, "february": 2, "feb": 2,
    "maret": 3, "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5, "may": 5,
    "juni": 6, "june": 6, "jun": 6,
    "juli": 7, "july": 7, "jul": 7,
    "agustus": 8, "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "october": 10, "oct": 10, "okt": 10,
    "november": 11, "nov": 11, "nop": 11,
    "desember": 12, "december": 12, "dec": 12, "des": 12,
}

# ============================================================
# SKILL DETECTOR
# ============================================================

class SkillDetector:
    """Detect and execute skills from natural language"""

    @classmethod
    async def detect_and_execute(cls, content: str) -> Optional[str]:
        lower = content.lower().strip()
        
        # Check each skill
        result = cls._check_time(lower)
        if result: return result
        
        result = cls._check_calendar(lower)
        if result: return result
        
        result = cls._check_countdown(lower)
        if result: return result
        
        result = await cls._check_weather(lower)
        if result: return result
        
        return None  # No skill matched

    # ============================================================
    # TIME DETECTION
    # ============================================================

    @classmethod
    def _check_time(cls, text: str) -> Optional[str]:
        time_patterns = [
            r'jam berapa',
            r'pukul berapa',
            r'waktu sekarang',
            r'what time',
            r'current time',
            r'time in ',
            r'jam di ',
            r'waktu di ',
            r'sekarang jam',
            r'what.s the time',
        ]
        
        if not any(re.search(p, text) for p in time_patterns):
            return None
        
        # Find timezone
        tz = "Asia/Jakarta"  # default
        for alias, tzname in TZ_ALIASES.items():
            if alias in text:
                tz = tzname
                break
        
        result = get_current_time(tz)
        if result["success"]:
            return f"🕐 **{result['full']}**"
        return None

    # ============================================================
    # CALENDAR DETECTION
    # ============================================================

    @classmethod
    def _check_calendar(cls, text: str) -> Optional[str]:
        cal_patterns = [
            r'tampilkan kalender',
            r'lihat kalender',
            r'show calendar',
            r'kalender bulan',
            r'calendar for',
            r'buka kalender',
            r'kalender\s+\w+',
        ]
        
        if not any(re.search(p, text) for p in cal_patterns):
            return None
        
        # Detect month
        month = None
        year = None
        
        for name, num in MONTH_NAMES.items():
            if name in text:
                month = num
                break
        
        # Detect year
        year_match = re.search(r'(20\d{2})', text)
        if year_match:
            year = int(year_match.group(1))
        
        # "bulan ini" / "this month"
        if "bulan ini" in text or "this month" in text:
            now = datetime.datetime.now()
            month = now.month
            year = now.year
        
        # "bulan depan" / "next month"
        if "bulan depan" in text or "next month" in text:
            now = datetime.datetime.now()
            if now.month == 12:
                month, year = 1, now.year + 1
            else:
                month, year = now.month + 1, now.year
        
        result = get_calendar(year, month)
        if result["success"]:
            return f"📅 **{result['month_name']} {result['year']}**\n{result['calendar_text']}"
        return None

    # ============================================================
    # COUNTDOWN DETECTION
    # ============================================================

    @classmethod
    def _check_countdown(cls, text: str) -> Optional[str]:
        cd_patterns = [
            r'berapa hari lagi',
            r'hitung mundur',
            r'countdown',
            r'how many days',
            r'days until',
            r'kapan .+ (lebaran|natal|tahun baru|imlek|valentine|halloween)',
        ]
        
        if not any(re.search(p, text) for p in cd_patterns):
            return None
        
        # Try to find date
        date_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', text)
        if date_match:
            target = date_match.group(0)
            result = days_until(target)
            if result["success"]:
                if result["is_today"]:
                    return f"🎉 Hari ini adalah **{target}**!"
                elif result["is_past"]:
                    return f"📅 {target} sudah lewat **{abs(result['days_remaining'])}** hari lalu"
                else:
                    return f"⏳ **{result['days_remaining']} hari** lagi menuju {target}"
        
        # Known events
        now = datetime.datetime.now()
        year = now.year
        events = {
            "tahun baru": f"{year+1}-01-01",
            "new year": f"{year+1}-01-01",
            "valentine": f"{year}-02-14" if now.month < 2 or (now.month == 2 and now.day < 14) else f"{year+1}-02-14",
            "natal": f"{year}-12-25" if now.month < 12 or (now.month == 12 and now.day < 25) else f"{year+1}-12-25",
            "christmas": f"{year}-12-25" if now.month < 12 or (now.month == 12 and now.day < 25) else f"{year+1}-12-25",
            "halloween": f"{year}-10-31" if now.month < 10 or (now.month == 10 and now.day < 31) else f"{year+1}-10-31",
            "kemerdekaan": f"{year}-08-17" if now.month < 8 or (now.month == 8 and now.day < 17) else f"{year+1}-08-17",
        }
        
        for event, date in events.items():
            if event in text:
                result = days_until(date)
                if result and result["success"]:
                    return f"⏳ **{result['days_remaining']} hari** lagi menuju {event.title()} ({date})"
        
        return None

    # ============================================================
    # WEATHER DETECTION
    # ============================================================

    @classmethod
    async def _check_weather(cls, text: str) -> Optional[str]:
        weather_patterns = [
            r'cuaca di (.+)',
            r'cuaca (.+)',
            r'weather in (.+)',
            r'weather (.+)',
            r'cuaca hari ini',
            r'gimana cuaca',
            r'how.s the weather',
            r'bagaimana cuaca',
        ]
        
        city = None
        for pattern in weather_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    city = match.group(1).strip().rstrip('?!.')
                except:
                    city = "Jakarta"
                break
        
        if not city:
            # Check if just asking about weather without city
            simple_patterns = [r'cuaca', r'weather', r'gimana cuaca', r'how.s the weather']
            if any(re.search(p, text) for p in simple_patterns):
                city = "Jakarta"
            else:
                return None
        
        # Clean city name
        city = re.sub(r'\b(sekarang|hari ini|today|now|gimana|bagaimana|how)\b', '', city).strip()
        if not city:
            city = "Jakarta"
        
        result = await get_weather(city)
        if result["success"]:
            return (
                f"🌤️ **Cuaca di {result['city']}**\n"
                f"**{result['description']}**\n"
                f"🌡️ Suhu: {result['temp']}°C (terasa {result['feels_like']}°C)\n"
                f"💧 Kelembapan: {result['humidity']}%\n"
                f"🌬️ Angin: {result['wind_speed']} km/h"
            )
        return None
