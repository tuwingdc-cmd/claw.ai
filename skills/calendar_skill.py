"""
Calendar Skills
"""
import datetime
import calendar

def get_calendar(year: int = None, month: int = None) -> dict:
    now = datetime.datetime.now()
    year = year or now.year
    month = month or now.month
    cal = calendar.TextCalendar()
    month_calendar = cal.formatmonth(year, month)
    return {
        "success": True,
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "calendar_text": f"```\n{month_calendar}```",
        "days_in_month": calendar.monthrange(year, month)[1]
    }

def days_until(target_date: str) -> dict:
    try:
        target = datetime.datetime.strptime(target_date, "%Y-%m-%d")
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        delta = (target - today).days
        return {"success": True, "target_date": target_date, "days_remaining": delta, "is_past": delta < 0, "is_today": delta == 0}
    except ValueError:
        return {"success": False, "error": "Format: YYYY-MM-DD"}
