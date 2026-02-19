"""
Weather Skills (wttr.in - free, no API key)
"""
import aiohttp
import asyncio

async def get_weather(city: str) -> dict:
    url = f"https://wttr.in/{city}?format=j1"
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    current = data["current_condition"][0]
                    return {
                        "success": True,
                        "city": city.title(),
                        "temp": current["temp_C"],
                        "feels_like": current["FeelsLikeC"],
                        "humidity": current["humidity"],
                        "description": current["weatherDesc"][0]["value"],
                        "wind_speed": current["windspeedKmph"],
                    }
                return {"success": False, "error": f"City not found: {city}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
