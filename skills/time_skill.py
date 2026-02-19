"""
Time & Date Skills
"""
import datetime
import pytz

def get_current_time(timezone: str = "Asia/Jakarta") -> dict:
    try:
        tz = pytz.timezone(timezone)
        now = datetime.datetime.now(tz)
        return {
            "success": True,
            "time": now.strftime("%H:%M:%S"),
            "date": now.strftime("%d %B %Y"),
            "day": now.strftime("%A"),
            "timezone": timezone,
            "full": now.strftime("%A, %d %B %Y - %H:%M:%S %Z")
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_time_difference(tz1: str, tz2: str) -> dict:
    try:
        now = datetime.datetime.now(pytz.UTC)
        time1 = now.astimezone(pytz.timezone(tz1))
        time2 = now.astimezone(pytz.timezone(tz2))
        diff = (time2.utcoffset() - time1.utcoffset()).total_seconds() / 3600
        return {"success": True, "tz1": tz1, "tz2": tz2, "difference_hours": diff,
                "time1": time1.strftime("%H:%M"), "time2": time2.strftime("%H:%M")}
    except Exception as e:
        return {"success": False, "error": str(e)}
