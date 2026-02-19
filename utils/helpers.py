"""
Utility Functions
Search engines, formatters, and helpers
"""

import aiohttp
import asyncio
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime

log = logging.getLogger(__name__)

# ============================================================
# MESSAGE FORMATTER
# ============================================================

class MessageFormatter:
    """Format AI responses for Discord"""
    
    @staticmethod
    def format_response(content: str, provider: str = None, model: str = None) -> str:
        """Format AI response with optional metadata"""
        
        # Clean up excessive newlines
        content = re.sub(r'\n{4,}', '\n\n\n', content)
        
        # Ensure code blocks are properly closed
        code_blocks = content.count('```')
        if code_blocks % 2 != 0:
            content += '\n```'
        
        return content
    
    @staticmethod
    def format_error(error: str) -> str:
        """Format error message"""
        return f"⚠️ **Error:** {error}"
    
    @staticmethod
    def format_search_results(results: List[Dict]) -> str:
        """Format search results"""
        if not results:
            return "No results found."
        
        lines = []
        for i, r in enumerate(results[:5], 1):
            title = r.get("title", "No title")
            body = r.get("body", r.get("snippet", ""))[:200]
            url = r.get("href", r.get("link", ""))
            
            lines.append(f"**{i}. {title}**\n{body}...\n🔗 {url}")
        
        return "\n\n".join(lines)

# ============================================================
# MESSAGE SPLITTER
# ============================================================

class MessageSplitter:
    """Split long messages for Discord (2000 char limit)"""
    
    @staticmethod
    def split(content: str, max_length: int = 2000) -> List[str]:
        """Split content into chunks"""
        
        if len(content) <= max_length:
            return [content]
        
        chunks = []
        
        while content:
            if len(content) <= max_length:
                chunks.append(content)
                break
            
            # Try to split at code block boundary
            split_point = content.rfind('```', 0, max_length)
            
            # If no code block, try newline
            if split_point == -1 or split_point < max_length // 2:
                split_point = content.rfind('\n', 0, max_length)
            
            # If no good split point, force split
            if split_point == -1 or split_point < max_length // 2:
                split_point = max_length
            
            chunks.append(content[:split_point])
            content = content[split_point:].lstrip()
        
        return chunks

# ============================================================
# SEARCH ENGINES
# ============================================================

class DuckDuckGoSearch:
    """DuckDuckGo search - Free, unlimited"""
    
    @staticmethod
    async def search(query: str, max_results: int = 5) -> List[Dict]:
        """Search using DuckDuckGo"""
        try:
            from duckduckgo_search import DDGS
            
            # Run in executor to not block
            loop = asyncio.get_event_loop()
            
            def _search():
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=max_results))
            
            results = await loop.run_in_executor(None, _search)
            return results
            
        except Exception as e:
            log.error(f"DuckDuckGo search error: {e}")
            return []

class TavilySearch:
    """Tavily AI search - 1000/month free"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.endpoint = "https://api.tavily.com/search"
    
    async def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search using Tavily"""
        if not self.api_key:
            return []
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic"
                }
                
                async with session.post(self.endpoint, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = []
                        for r in data.get("results", []):
                            results.append({
                                "title": r.get("title", ""),
                                "body": r.get("content", ""),
                                "href": r.get("url", "")
                            })
                        return results
                    return []
        except Exception as e:
            log.error(f"Tavily search error: {e}")
            return []

class BraveSearch:
    """Brave Search - 2000/month free"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.endpoint = "https://api.search.brave.com/res/v1/web/search"
    
    async def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search using Brave"""
        if not self.api_key:
            return []
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Accept": "application/json",
                    "X-Subscription-Token": self.api_key
                }
                params = {"q": query, "count": max_results}
                
                async with session.get(self.endpoint, headers=headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = []
                        for r in data.get("web", {}).get("results", []):
                            results.append({
                                "title": r.get("title", ""),
                                "body": r.get("description", ""),
                                "href": r.get("url", "")
                            })
                        return results
                    return []
        except Exception as e:
            log.error(f"Brave search error: {e}")
            return []

class SerperSearch:
    """Serper Google Search - 2500 one-time free"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.endpoint = "https://google.serper.dev/search"
    
    async def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search using Serper"""
        if not self.api_key:
            return []
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json"
                }
                payload = {"q": query, "num": max_results}
                
                async with session.post(self.endpoint, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = []
                        for r in data.get("organic", []):
                            results.append({
                                "title": r.get("title", ""),
                                "body": r.get("snippet", ""),
                                "href": r.get("link", "")
                            })
                        return results
                    return []
        except Exception as e:
            log.error(f"Serper search error: {e}")
            return []

class JinaSearch:
    """Jina AI Search - Rate limited free"""
    
    @staticmethod
    async def search(query: str) -> List[Dict]:
        """Search using Jina"""
        try:
            import urllib.parse
            encoded = urllib.parse.quote(query)
            url = f"https://s.jina.ai/{encoded}"
            
            async with aiohttp.ClientSession() as session:
                headers = {"Accept": "application/json"}
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Jina returns different format
                        results = []
                        for r in data.get("data", [])[:5]:
                            results.append({
                                "title": r.get("title", ""),
                                "body": r.get("content", "")[:300],
                                "href": r.get("url", "")
                            })
                        return results
                    return []
        except Exception as e:
            log.error(f"Jina search error: {e}")
            return []

# ============================================================
# SEARCH MANAGER
# ============================================================

class SearchManager:
    """Manages multiple search engines with fallback"""
    
    def __init__(self, api_keys: Dict[str, str]):
        self.engines = {
            "duckduckgo": DuckDuckGoSearch(),
            "tavily": TavilySearch(api_keys.get("tavily", "")),
            "brave": BraveSearch(api_keys.get("brave", "")),
            "serper": SerperSearch(api_keys.get("serper", "")),
            "jina": JinaSearch(),
        }
        
        self.fallback_order = ["duckduckgo", "tavily", "brave", "serper", "jina"]
    
    async def search(
        self, 
        query: str, 
        engine: str = "duckduckgo",
        max_results: int = 5
    ) -> str:
        """
        Search with fallback
        Returns formatted string of results
        """
        
        # Try preferred engine
        results = await self._search_engine(engine, query, max_results)
        
        # Fallback if no results
        if not results:
            for backup_engine in self.fallback_order:
                if backup_engine != engine:
                    results = await self._search_engine(backup_engine, query, max_results)
                    if results:
                        break
        
        if results:
            return MessageFormatter.format_search_results(results)
        
        return "No search results found."
    
    async def _search_engine(
        self, 
        engine: str, 
        query: str, 
        max_results: int
    ) -> List[Dict]:
        """Call specific search engine"""
        
        if engine == "duckduckgo":
            return await DuckDuckGoSearch.search(query, max_results)
        elif engine == "jina":
            return await JinaSearch.search(query)
        else:
            eng = self.engines.get(engine)
            if eng and hasattr(eng, 'search'):
                return await eng.search(query, max_results)
        
        return []

# ============================================================
# RATE LIMITER
# ============================================================

class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self):
        self._requests: Dict[str, List[datetime]] = {}
    
    def check(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        """
        Check if request is allowed
        Returns True if allowed, False if rate limited
        """
        now = datetime.now()
        
        if key not in self._requests:
            self._requests[key] = []
        
        # Clean old requests
        cutoff = now.timestamp() - window_seconds
        self._requests[key] = [
            t for t in self._requests[key] 
            if t.timestamp() > cutoff
        ]
        
        # Check limit
        if len(self._requests[key]) >= limit:
            return False
        
        # Record request
        self._requests[key].append(now)
        return True
    
    def get_remaining(self, key: str, limit: int, window_seconds: int = 60) -> int:
        """Get remaining requests in window"""
        now = datetime.now()
        
        if key not in self._requests:
            return limit
        
        cutoff = now.timestamp() - window_seconds
        current = len([
            t for t in self._requests[key] 
            if t.timestamp() > cutoff
        ])
        
        return max(0, limit - current)

# ============================================================
# MISC HELPERS
# ============================================================

def truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to max length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def clean_content(content: str) -> str:
    """Clean user input"""
    # Remove excessive whitespace
    content = " ".join(content.split())
    # Remove potential injection attempts
    content = content.replace("```", "` ` `")
    return content.strip()

def extract_code_blocks(content: str) -> List[str]:
    """Extract code blocks from content"""
    pattern = r'```(?:\w+)?\n?(.*?)```'
    return re.findall(pattern, content, re.DOTALL)

def get_timestamp() -> str:
    """Get current timestamp string"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
