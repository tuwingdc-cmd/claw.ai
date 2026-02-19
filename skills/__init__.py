"""Skills Package"""
from .time_skill import get_current_time, get_time_difference
from .alarm_skill import set_alarm, list_alarms, cancel_alarm
from .calendar_skill import get_calendar, days_until
from .weather_skill import get_weather
from .detector import SkillDetector
