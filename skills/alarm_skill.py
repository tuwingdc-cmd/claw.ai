"""
Alarm & Reminder Skills
"""

import asyncio
from datetime import datetime, timedelta
from typing import Callable

# In-memory storage
alarms = {}  # {guild_id: {user_id: [alarm_data]}}

async def set_alarm(
    guild_id: int,
    user_id: int,
    minutes: int,
    message: str,
    callback: Callable
) -> dict:
    """Set alarm yang akan trigger setelah X menit"""
    
    alarm_id = f"{user_id}_{datetime.now().timestamp()}"
    trigger_time = datetime.now() + timedelta(minutes=minutes)
    
    alarm_data = {
        "id": alarm_id,
        "user_id": user_id,
        "message": message,
        "trigger_time": trigger_time,
        "created_at": datetime.now()
    }
    
    # Store alarm
    if guild_id not in alarms:
        alarms[guild_id] = {}
    if user_id not in alarms[guild_id]:
        alarms[guild_id][user_id] = []
    alarms[guild_id][user_id].append(alarm_data)
    
    # Schedule the alarm
    asyncio.create_task(_alarm_worker(guild_id, alarm_data, callback))
    
    return {
        "success": True,
        "alarm_id": alarm_id,
        "trigger_time": trigger_time.strftime("%H:%M:%S"),
        "message": message
    }

async def _alarm_worker(guild_id: int, alarm_data: dict, callback: Callable):
    """Background worker untuk trigger alarm"""
    delay = (alarm_data["trigger_time"] - datetime.now()).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)
        await callback(alarm_data)
        
        # Remove from storage
        user_id = alarm_data["user_id"]
        if guild_id in alarms and user_id in alarms[guild_id]:
            alarms[guild_id][user_id] = [
                a for a in alarms[guild_id][user_id] 
                if a["id"] != alarm_data["id"]
            ]

def list_alarms(guild_id: int, user_id: int) -> list:
    """List semua alarm aktif user"""
    if guild_id in alarms and user_id in alarms[guild_id]:
        return [a for a in alarms[guild_id][user_id] 
                if a["trigger_time"] > datetime.now()]
    return []

def cancel_alarm(guild_id: int, user_id: int, alarm_id: str) -> bool:
    """Cancel alarm by ID"""
    if guild_id in alarms and user_id in alarms[guild_id]:
        alarms[guild_id][user_id] = [
            a for a in alarms[guild_id][user_id] 
            if a["id"] != alarm_id
        ]
        return True
    return False
