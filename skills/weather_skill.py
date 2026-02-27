"""
Weather Skills
Primary: Open-Meteo (free, no API key, accurate)
Fallback: OpenWeatherMap (needs API key, more details)
"""
import aiohttp
import asyncio
import logging
from typing import Dict, Optional

log = logging.getLogger(__name__)

# Weather code descriptions (WMO standard used by Open-Meteo)
WMO_CODES = {
    0: "Cerah ☀️",
    1: "Cerah berawan 🌤️",
    2: "Berawan sebagian ⛅",
    3: "Mendung ☁️",
    45: "Berkabut 🌫️",
    48: "Kabut tebal 🌫️",
    51: "Gerimis ringan 🌧️",
    53: "Gerimis 🌧️",
    55: "Gerimis lebat 🌧️",
    61: "Hujan ringan 🌧️",
    63: "Hujan sedang 🌧️",
    65: "Hujan lebat 🌧️",
    66: "Hujan es ringan 🌨️",
    67: "Hujan es lebat 🌨️",
    71: "Salju ringan 🌨️",
    73: "Salju sedang 🌨️",
    75: "Salju lebat 🌨️",
    77: "Butiran salju ❄️",
    80: "Hujan ringan 🌦️",
    81: "Hujan sedang 🌧️",
    82: "Hujan sangat lebat ⛈️",
    85: "Salju ringan 🌨️",
    86: "Salju lebat 🌨️",
    95: "Badai petir ⛈️",
    96: "Badai petir + hujan es ⛈️",
    99: "Badai petir hebat ⛈️",
}


async def get_coordinates(city: str, owm_api_key: Optional[str] = None) -> Optional[Dict]:
    """Get coordinates from city name using OpenWeatherMap Geocoding API or Nominatim"""
    
    # Try OpenWeatherMap Geocoding first (if API key available)
    if owm_api_key:
        try:
            url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={owm_api_key}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data:
                            return {
                                "lat": data[0]["lat"],
                                "lon": data[0]["lon"],
                                "name": data[0].get("local_names", {}).get("id") or data[0]["name"],
                                "country": data[0].get("country", "")
                            }
        except Exception as e:
            log.warning(f"OWM Geocoding error: {e}")
    
    # Fallback: Nominatim (OpenStreetMap) - free, no API key
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1"
        headers = {"User-Agent": "DiscordWeatherBot/1.0"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data:
                        return {
                            "lat": float(data[0]["lat"]),
                            "lon": float(data[0]["lon"]),
                            "name": data[0]["display_name"].split(",")[0],
                            "country": ""
                        }
    except Exception as e:
        log.warning(f"Nominatim Geocoding error: {e}")
    
    return None


async def get_weather_open_meteo(lat: float, lon: float, city_name: str) -> Dict:
    """Get weather from Open-Meteo (free, no API key, accurate)"""
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
            f"weather_code,wind_speed_10m,wind_direction_10m,pressure_msl"
            f"&timezone=auto"
        )
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    current = data.get("current", {})
                    
                    weather_code = current.get("weather_code", 0)
                    description = WMO_CODES.get(weather_code, "Unknown")
                    
                    return {
                        "success": True,
                        "source": "Open-Meteo",
                        "city": city_name,
                        "temp": round(current.get("temperature_2m", 0)),
                        "feels_like": round(current.get("apparent_temperature", 0)),
                        "humidity": current.get("relative_humidity_2m", 0),
                        "description": description,
                        "wind_speed": round(current.get("wind_speed_10m", 0)),
                        "wind_direction": current.get("wind_direction_10m", 0),
                        "pressure": current.get("pressure_msl", 0),
                        "weather_code": weather_code,
                    }
                else:
                    return {"success": False, "error": f"Open-Meteo HTTP {resp.status}"}
    except Exception as e:
        return {"success": False, "error": f"Open-Meteo error: {e}"}


async def get_weather_openweathermap(city: str, api_key: str) -> Dict:
    """Get weather from OpenWeatherMap (needs API key, more details)"""
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=id"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    return {
                        "success": True,
                        "source": "OpenWeatherMap",
                        "city": data.get("name", city),
                        "temp": round(data["main"]["temp"]),
                        "feels_like": round(data["main"]["feels_like"]),
                        "humidity": data["main"]["humidity"],
                        "description": data["weather"][0]["description"].title(),
                        "wind_speed": round(data["wind"]["speed"] * 3.6),  # m/s to km/h
                        "wind_direction": data["wind"].get("deg", 0),
                        "pressure": data["main"]["pressure"],
                        "visibility": data.get("visibility", 0) / 1000,  # m to km
                        "icon": data["weather"][0]["icon"],
                        "country": data["sys"].get("country", ""),
                    }
                elif resp.status == 404:
                    return {"success": False, "error": f"Kota tidak ditemukan: {city}"}
                else:
                    return {"success": False, "error": f"OpenWeatherMap HTTP {resp.status}"}
    except Exception as e:
        return {"success": False, "error": f"OpenWeatherMap error: {e}"}


async def get_weather(city: str, api_key: Optional[str] = None) -> Dict:
    """
    Get weather for a city
    
    Strategy:
    1. If OWM API key provided → use OpenWeatherMap (more details)
    2. Fallback → Open-Meteo (free, no key needed)
    
    Args:
        city: City name (e.g., "Jakarta", "Tokyo", "New York")
        api_key: OpenWeatherMap API key (optional)
    
    Returns:
        Dict with weather data or error
    """
    
    # Get API key from config if not provided
    if not api_key:
        try:
            from config import API_KEYS
            api_key = API_KEYS.get("openweathermap")
        except:
            pass
    
    # Strategy 1: OpenWeatherMap (if API key available)
    if api_key:
        log.info(f"🌤️ Trying OpenWeatherMap for {city}")
        result = await get_weather_openweathermap(city, api_key)
        if result["success"]:
            log.info(f"🌤️ OpenWeatherMap success for {city}")
            return result
        else:
            log.warning(f"🌤️ OpenWeatherMap failed: {result.get('error')}")
    
    # Strategy 2: Open-Meteo (free, needs coordinates)
    log.info(f"🌤️ Trying Open-Meteo for {city}")
    
    # Get coordinates first
    coords = await get_coordinates(city, api_key)
    if not coords:
        return {"success": False, "error": f"Kota tidak ditemukan: {city}"}
    
    result = await get_weather_open_meteo(coords["lat"], coords["lon"], coords["name"])
    if result["success"]:
        log.info(f"🌤️ Open-Meteo success for {city}")
    
    return result


async def get_forecast(city: str, days: int = 3, api_key: Optional[str] = None) -> Dict:
    """Get weather forecast for next N days"""
    
    # Get API key from config if not provided
    if not api_key:
        try:
            from config import API_KEYS
            api_key = API_KEYS.get("openweathermap")
        except:
            pass
    
    # Get coordinates
    coords = await get_coordinates(city, api_key)
    if not coords:
        return {"success": False, "error": f"Kota tidak ditemukan: {city}"}
    
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={coords['lat']}&longitude={coords['lon']}"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,"
            f"precipitation_probability_max,wind_speed_10m_max"
            f"&timezone=auto&forecast_days={days}"
        )
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    daily = data.get("daily", {})
                    
                    forecasts = []
                    dates = daily.get("time", [])
                    
                    for i, date in enumerate(dates):
                        weather_code = daily["weather_code"][i]
                        forecasts.append({
                            "date": date,
                            "description": WMO_CODES.get(weather_code, "Unknown"),
                            "temp_max": round(daily["temperature_2m_max"][i]),
                            "temp_min": round(daily["temperature_2m_min"][i]),
                            "rain_chance": daily["precipitation_probability_max"][i],
                            "wind_max": round(daily["wind_speed_10m_max"][i]),
                        })
                    
                    return {
                        "success": True,
                        "city": coords["name"],
                        "forecasts": forecasts,
                    }
                else:
                    return {"success": False, "error": f"Forecast HTTP {resp.status}"}
    except Exception as e:
        return {"success": False, "error": f"Forecast error: {e}"}
