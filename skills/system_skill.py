"""
System Self-Awareness Skill
Bot bisa melihat status sistem, log, dan error sendiri
"""
import os
import subprocess
import psutil
from datetime import datetime
from typing import Dict, Optional
import logging

log = logging.getLogger(__name__)

# Path konfigurasi
BOT_DIR = "/root/claw.ai"
LOG_SERVICE = "clawai.service"

def get_system_status() -> Dict:
    """Get system resource usage"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get bot process info
        bot_process = None
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
            try:
                if 'python' in proc.info['name'].lower():
                    cmdline = proc.cmdline()
                    if any('main.py' in arg for arg in cmdline):
                        bot_process = {
                            "pid": proc.info['pid'],
                            "memory_mb": proc.info['memory_info'].rss / 1024 / 1024,
                            "cpu_percent": proc.cpu_percent()
                        }
                        break
            except:
                pass
        
        return {
            "success": True,
            "cpu_percent": cpu_percent,
            "memory_total_gb": round(memory.total / 1024**3, 2),
            "memory_used_gb": round(memory.used / 1024**3, 2),
            "memory_percent": memory.percent,
            "disk_total_gb": round(disk.total / 1024**3, 2),
            "disk_used_gb": round(disk.used / 1024**3, 2),
            "disk_percent": round(disk.percent, 1),
            "bot_process": bot_process,
            "uptime": get_uptime(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_uptime() -> str:
    """Get system uptime"""
    try:
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{days}d {hours}h {minutes}m"
    except:
        return "unknown"


def get_service_status() -> Dict:
    """Get bot service status from systemd"""
    try:
        result = subprocess.run(
            ["systemctl", "status", LOG_SERVICE, "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Parse status
        output = result.stdout
        is_active = "active (running)" in output.lower()
        
        # Get service uptime
        uptime_line = [l for l in output.split('\n') if 'Active:' in l]
        service_uptime = uptime_line[0] if uptime_line else "unknown"
        
        return {
            "success": True,
            "is_running": is_active,
            "status_text": "running" if is_active else "stopped",
            "details": service_uptime.strip(),
            "full_output": output[:1000]  # Limit output
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_recent_logs(lines: int = 50, filter_error: bool = False) -> Dict:
    """Get recent bot logs from journalctl"""
    try:
        cmd = ["journalctl", "-u", LOG_SERVICE, "-n", str(lines), "--no-pager"]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15
        )
        
        log_lines = result.stdout.strip().split('\n')
        
        if filter_error:
            # Filter hanya ERROR dan WARNING
            log_lines = [
                l for l in log_lines 
                if 'ERROR' in l or 'WARNING' in l or 'Error' in l or 'Exception' in l or 'Traceback' in l
            ]
        
        return {
            "success": True,
            "lines": log_lines[-lines:],  # Last N lines
            "total_lines": len(log_lines),
            "log_text": '\n'.join(log_lines[-lines:])
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_recent_errors(lines: int = 20) -> Dict:
    """Get only error logs"""
    return get_recent_logs(lines=100, filter_error=True)


def read_bot_file(filename: str) -> Dict:
    """Read a bot source file (untuk debugging)"""
    # Security: hanya allow file tertentu
    ALLOWED_FILES = [
        "main.py", "config.py", 
        "core/handler.py", "core/providers.py", "core/database.py",
        "skills/system_skill.py", "skills/time_skill.py", "skills/weather_skill.py",
        "music/player.py", "music/commands.py",
        ".env.example", "requirements.txt"
    ]
    
    # Normalize path
    filename = filename.lstrip('/')
    
    if filename not in ALLOWED_FILES:
        return {
            "success": False, 
            "error": f"File tidak diizinkan. Allowed: {', '.join(ALLOWED_FILES)}"
        }
    
    filepath = os.path.join(BOT_DIR, filename)
    
    try:
        if not os.path.exists(filepath):
            return {"success": False, "error": f"File tidak ditemukan: {filename}"}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Limit content
        if len(content) > 10000:
            content = content[:10000] + "\n\n[... file trimmed ...]"
        
        return {
            "success": True,
            "filename": filename,
            "content": content,
            "size_bytes": os.path.getsize(filepath)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def restart_bot_service() -> Dict:
    """Restart bot service (DANGEROUS - require confirmation)"""
    try:
        result = subprocess.run(
            ["systemctl", "restart", LOG_SERVICE],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return {"success": True, "message": "Bot service restarted successfully"}
        else:
            return {"success": False, "error": result.stderr}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_git_status() -> Dict:
    """Get git status of bot repository"""
    try:
        os.chdir(BOT_DIR)
        
        # Current branch
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=10
        ).stdout.strip()
        
        # Last commit
        last_commit = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%h - %s (%cr)"],
            capture_output=True, text=True, timeout=10
        ).stdout.strip()
        
        # Check for updates
        subprocess.run(["git", "fetch"], capture_output=True, timeout=30)
        
        status = subprocess.run(
            ["git", "status", "-sb"],
            capture_output=True, text=True, timeout=10
        ).stdout.strip()
        
        behind = "behind" in status.lower()
        ahead = "ahead" in status.lower()
        
        return {
            "success": True,
            "branch": branch,
            "last_commit": last_commit,
            "has_updates": behind,
            "ahead_of_remote": ahead,
            "status": status
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def git_pull_update() -> Dict:
    """Pull latest updates from git (DANGEROUS)"""
    try:
        os.chdir(BOT_DIR)
        
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            return {
                "success": True, 
                "message": "Git pull successful",
                "output": result.stdout
            }
        else:
            return {
                "success": False, 
                "error": result.stderr,
                "output": result.stdout
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_provider_health() -> Dict:
    """Check all AI provider health status"""
    try:
        from config import PROVIDERS, API_KEYS
        
        results = {}
        for name, config in PROVIDERS.items():
            has_key = bool(API_KEYS.get(name))
            results[name] = {
                "has_api_key": has_key,
                "base_url": config.get("base_url", "N/A")[:50],
                "rate_limit": config.get("rate_limit", "N/A")
            }
        
        return {
            "success": True,
            "providers": results,
            "total": len(results),
            "configured": sum(1 for v in results.values() if v["has_api_key"])
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# FORMATTED OUTPUT UNTUK AI
# ============================================================

def format_system_report() -> str:
    """Generate full system report untuk AI"""
    parts = ["## 🖥️ System Status Report\n"]
    
    # System resources
    sys_status = get_system_status()
    if sys_status["success"]:
        parts.append(f"**Resources:**")
        parts.append(f"- CPU: {sys_status['cpu_percent']}%")
        parts.append(f"- Memory: {sys_status['memory_used_gb']}/{sys_status['memory_total_gb']} GB ({sys_status['memory_percent']}%)")
        parts.append(f"- Disk: {sys_status['disk_used_gb']}/{sys_status['disk_total_gb']} GB ({sys_status['disk_percent']}%)")
        parts.append(f"- Uptime: {sys_status['uptime']}")
        
        if sys_status.get('bot_process'):
            bp = sys_status['bot_process']
            parts.append(f"- Bot PID: {bp['pid']} | Memory: {bp['memory_mb']:.1f} MB")
    
    parts.append("")
    
    # Service status
    svc = get_service_status()
    if svc["success"]:
        status_icon = "🟢" if svc["is_running"] else "🔴"
        parts.append(f"**Service:** {status_icon} {svc['status_text']}")
        parts.append(f"- {svc['details']}")
    
    parts.append("")
    
    # Git status
    git = get_git_status()
    if git["success"]:
        update_icon = "⚠️ Updates available!" if git["has_updates"] else "✅ Up to date"
        parts.append(f"**Git:** {git['branch']} | {update_icon}")
        parts.append(f"- Last commit: {git['last_commit']}")
    
    parts.append("")
    
    # Provider health
    prov = get_provider_health()
    if prov["success"]:
        parts.append(f"**Providers:** {prov['configured']}/{prov['total']} configured")
    
    return "\n".join(parts)


def format_error_report() -> str:
    """Generate error report dari recent logs"""
    errors = get_recent_errors(lines=30)
    
    if not errors["success"]:
        return f"Failed to get logs: {errors['error']}"
    
    if not errors["lines"]:
        return "✅ No recent errors found in logs!"
    
    parts = ["## ⚠️ Recent Errors\n"]
    parts.append(f"Found {len(errors['lines'])} error entries:\n")
    parts.append("```")
    parts.append('\n'.join(errors['lines'][-20:]))  # Last 20
    parts.append("```")
    
    return "\n".join(parts)
