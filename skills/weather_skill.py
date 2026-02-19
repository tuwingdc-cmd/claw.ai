"""
Weather Skills (menggunakan wttr.in - no API key needed)
"""

import aiohttp

async def get_weather(city: str) -> dict:
    """Ambil cuaca dari wttr.in (free, no API key)"""
    
    # wttr.in format: https://wttr.in/Jakarta?format=j1
    url = f"https://wttr.in/{city}?format=j1"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    current = data["current_condition"][0]
                    
                    return {
                        "success": True,
                        "city": city,
                        "temp": current["temp_C"],
                        "feels_like": current["FeelsLikeC"],
                        "humidity": current["humidity"],
                        "description": current["weatherDesc"][0]["value"],
                        "wind_speed": current["windspeedKmph"],
                    }
                else:
                    return {"success": False, "error": f"City not found: {city}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
