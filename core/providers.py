"""
All AI Provider Implementations
Single file containing all provider classes
"""

import aiohttp
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

log = logging.getLogger(__name__)

# ============================================================
# BASE PROVIDER
# ============================================================

@dataclass
class AIResponse:
    """Standardized response from any provider"""
    success: bool
    content: str
    provider: str
    model: str
    error: Optional[str] = None
    tokens_used: int = 0
    latency: float = 0.0

class BaseProvider(ABC):
    """Abstract base class for all AI providers"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.name = "base"
        self.endpoint = ""
    
    @abstractmethod
    async def chat(
        self, 
        messages: List[Dict[str, str]], 
        model: str,
        **kwargs
    ) -> AIResponse:
        """Send chat completion request"""
        pass
    
    async def health_check(self) -> bool:
        """Check if provider is available"""
        return self.api_key is not None or self.name in ["pollinations", "mlvoca"]
    
    def _build_headers(self) -> Dict[str, str]:
        """Build authorization headers"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

# ============================================================
# OPENAI-COMPATIBLE PROVIDER (Base for most providers)
# ============================================================

class OpenAICompatibleProvider(BaseProvider):
    """Base class for OpenAI-compatible APIs (Groq, OpenRouter, etc.)"""
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AIResponse:
        """Send chat request to OpenAI-compatible endpoint"""
        
        import time
        start = time.time()
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,
                    headers=self._build_headers(),
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    latency = time.time() - start
                    
                    if resp.status == 200:
                        data = await resp.json()
                        content = data["choices"][0]["message"]["content"]
                        tokens = data.get("usage", {}).get("total_tokens", 0)
                        
                        return AIResponse(
                            success=True,
                            content=content,
                            provider=self.name,
                            model=model,
                            tokens_used=tokens,
                            latency=latency
                        )
                    else:
                        error_text = await resp.text()
                        log.warning(f"{self.name} error {resp.status}: {error_text[:200]}")
                        
                        return AIResponse(
                            success=False,
                            content="",
                            provider=self.name,
                            model=model,
                            error=f"HTTP {resp.status}: {error_text[:100]}",
                            latency=latency
                        )
                        
        except asyncio.TimeoutError:
            return AIResponse(
                success=False,
                content="",
                provider=self.name,
                model=model,
                error="Request timeout"
            )
        except Exception as e:
            log.error(f"{self.name} exception: {e}")
            return AIResponse(
                success=False,
                content="",
                provider=self.name,
                model=model,
                error=str(e)
            )

# ============================================================
# GROQ PROVIDER
# ============================================================

class GroqProvider(OpenAICompatibleProvider):
    """Groq API - Ultra fast inference"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.name = "groq"
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"

# ============================================================
# OPENROUTER PROVIDER
# ============================================================

class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter API - Multi-model gateway"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.name = "openrouter"
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"
    
    def _build_headers(self) -> Dict[str, str]:
        headers = super()._build_headers()
        headers["HTTP-Referer"] = "https://discord-bot.local"
        headers["X-Title"] = "Discord AI Bot"
        return headers

# ============================================================
# POLLINATIONS PROVIDER
# ============================================================

class PollinationsProvider(OpenAICompatibleProvider):
    """Pollinations API - Free AI gateway (works with/without key)"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.name = "pollinations"
        self.endpoint = "https://gen.pollinations.ai/v1/chat/completions"
    
    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        # Works without key (anonymous mode)
        return headers
    
    async def health_check(self) -> bool:
        """Pollinations always available (anonymous mode)"""
        return True

# ============================================================
# CEREBRAS PROVIDER
# ============================================================

class CerebrasProvider(OpenAICompatibleProvider):
    """Cerebras API - 1M tokens/day free"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.name = "cerebras"
        self.endpoint = "https://api.cerebras.ai/v1/chat/completions"

# ============================================================
# HUGGINGFACE PROVIDER
# ============================================================

class HuggingFaceProvider(OpenAICompatibleProvider):
    """HuggingFace Inference API"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.name = "huggingface"
        self.endpoint = "https://router.huggingface.co/v1/chat/completions"

# ============================================================
# COHERE PROVIDER
# ============================================================

class CohereProvider(BaseProvider):
    """Cohere API - Uses v2 chat endpoint"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.name = "cohere"
        self.endpoint = "https://api.cohere.ai/v2/chat"
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AIResponse:
        """Cohere uses different message format"""
        
        import time
        start = time.time()
        
        # Convert to Cohere format
        cohere_messages = []
        for msg in messages:
            role = "assistant" if msg["role"] == "assistant" else "user"
            if msg["role"] == "system":
                role = "system"
            cohere_messages.append({
                "role": role,
                "content": msg["content"]
            })
        
        payload = {
            "model": model,
            "messages": cohere_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Client-Name": "discord-bot"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    latency = time.time() - start
                    
                    if resp.status == 200:
                        data = await resp.json()
                        content = data["message"]["content"][0]["text"]
                        
                        return AIResponse(
                            success=True,
                            content=content,
                            provider=self.name,
                            model=model,
                            latency=latency
                        )
                    else:
                        error_text = await resp.text()
                        return AIResponse(
                            success=False,
                            content="",
                            provider=self.name,
                            model=model,
                            error=f"HTTP {resp.status}",
                            latency=latency
                        )
                        
        except Exception as e:
            return AIResponse(
                success=False,
                content="",
                provider=self.name,
                model=model,
                error=str(e)
            )

# ============================================================
# SILICONFLOW PROVIDER
# ============================================================

class SiliconFlowProvider(OpenAICompatibleProvider):
    """SiliconFlow API - China-based, free tier"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.name = "siliconflow"
        self.endpoint = "https://api.siliconflow.cn/v1/chat/completions"

# ============================================================
# ROUTEWAY PROVIDER
# ============================================================

class RoutewayProvider(OpenAICompatibleProvider):
    """Routeway API - Multi-model with free credits"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.name = "routeway"
        self.endpoint = "https://api.routeway.ai/v1/chat/completions"

# ============================================================
# GEMINI PROVIDER
# ============================================================

class GeminiProvider(BaseProvider):
    """Google Gemini API - Different format"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.name = "gemini"
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AIResponse:
        """Gemini uses generateContent endpoint"""
        
        import time
        start = time.time()
        
        # Convert messages to Gemini format
        contents = []
        system_instruction = None
        
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            else:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}]
                })
        
        endpoint = f"{self.base_url}/{model}:generateContent?key={self.api_key}"
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    latency = time.time() - start
                    
                    if resp.status == 200:
                        data = await resp.json()
                        content = data["candidates"][0]["content"]["parts"][0]["text"]
                        
                        return AIResponse(
                            success=True,
                            content=content,
                            provider=self.name,
                            model=model,
                            latency=latency
                        )
                    else:
                        error_text = await resp.text()
                        return AIResponse(
                            success=False,
                            content="",
                            provider=self.name,
                            model=model,
                            error=f"HTTP {resp.status}",
                            latency=latency
                        )
                        
        except Exception as e:
            return AIResponse(
                success=False,
                content="",
                provider=self.name,
                model=model,
                error=str(e)
            )

# ============================================================
# CLOUDFLARE PROVIDER
# ============================================================

class CloudflareProvider(BaseProvider):
    """Cloudflare Workers AI"""
    
    def __init__(self, api_key: str, account_id: str):
        super().__init__(api_key)
        self.name = "cloudflare"
        self.account_id = account_id
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run"
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AIResponse:
        """Cloudflare uses /ai/run/{model} endpoint"""
        
        import time
        start = time.time()
        
        endpoint = f"{self.base_url}/{model}"
        
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    latency = time.time() - start
                    
                    if resp.status == 200:
                        data = await resp.json()
                        content = data["result"]["response"]
                        
                        return AIResponse(
                            success=True,
                            content=content,
                            provider=self.name,
                            model=model,
                            latency=latency
                        )
                    else:
                        error_text = await resp.text()
                        return AIResponse(
                            success=False,
                            content="",
                            provider=self.name,
                            model=model,
                            error=f"HTTP {resp.status}",
                            latency=latency
                        )
                        
        except Exception as e:
            return AIResponse(
                success=False,
                content="",
                provider=self.name,
                model=model,
                error=str(e)
            )

# ============================================================
# MLVOCA PROVIDER (No API Key)
# ============================================================

class MLVOCAProvider(BaseProvider):
    """MLVOCA API - Completely free, no key needed"""
    
    def __init__(self):
        super().__init__(None)
        self.name = "mlvoca"
        self.endpoint = "https://mlvoca.com/api/generate"
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        **kwargs
    ) -> AIResponse:
        """MLVOCA uses simple generate endpoint"""
        
        import time
        start = time.time()
        
        # Get last user message as prompt
        prompt = messages[-1]["content"] if messages else ""
        
        # Add system context if exists
        for msg in messages:
            if msg["role"] == "system":
                prompt = f"{msg['content']}\n\n{prompt}"
                break
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    latency = time.time() - start
                    
                    if resp.status == 200:
                        data = await resp.json()
                        content = data.get("response", "")
                        
                        return AIResponse(
                            success=True,
                            content=content,
                            provider=self.name,
                            model=model,
                            latency=latency
                        )
                    else:
                        return AIResponse(
                            success=False,
                            content="",
                            provider=self.name,
                            model=model,
                            error=f"HTTP {resp.status}",
                            latency=latency
                        )
                        
        except Exception as e:
            return AIResponse(
                success=False,
                content="",
                provider=self.name,
                model=model,
                error=str(e)
            )
    
    async def health_check(self) -> bool:
        return True  # Always available

# ============================================================
# PROVIDER FACTORY
# ============================================================

class ProviderFactory:
    """Factory to create provider instances"""
    
    _instances: Dict[str, BaseProvider] = {}
    
    @classmethod
    def get(cls, provider_name: str, api_keys: Dict[str, str]) -> Optional[BaseProvider]:
        """Get or create provider instance"""
        
        if provider_name in cls._instances:
            return cls._instances[provider_name]
        
        provider = None
        
        if provider_name == "groq":
            key = api_keys.get("groq")
            if key:
                provider = GroqProvider(key)
                
        elif provider_name == "openrouter":
            key = api_keys.get("openrouter")
            if key:
                provider = OpenRouterProvider(key)
                
        elif provider_name == "pollinations":
            key = api_keys.get("pollinations")
            provider = PollinationsProvider(key)  # Works without key
            
        elif provider_name == "gemini":
            key = api_keys.get("gemini")
            if key:
                provider = GeminiProvider(key)
                
        elif provider_name == "cerebras":
            key = api_keys.get("cerebras")
            if key:
                provider = CerebrasProvider(key)
                
        elif provider_name == "cloudflare":
            key = api_keys.get("cloudflare")
            account = api_keys.get("cloudflare_account")
            if key and account:
                provider = CloudflareProvider(key, account)
                
        elif provider_name == "huggingface":
            key = api_keys.get("huggingface")
            if key:
                provider = HuggingFaceProvider(key)
                
        elif provider_name == "cohere":
            key = api_keys.get("cohere")
            if key:
                provider = CohereProvider(key)
                
        elif provider_name == "siliconflow":
            key = api_keys.get("siliconflow")
            if key:
                provider = SiliconFlowProvider(key)
                
        elif provider_name == "routeway":
            key = api_keys.get("routeway")
            if key:
                provider = RoutewayProvider(key)
                
        elif provider_name == "mlvoca":
            provider = MLVOCAProvider()
        
        if provider:
            cls._instances[provider_name] = provider
        
        return provider
    
    @classmethod
    def clear_cache(cls):
        """Clear cached instances"""
        cls._instances.clear()
