"""
All AI Provider Implementations
Single file containing all provider classes
— Verified Feb 22, 2026 —
"""

import os
import aiohttp
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

log = logging.getLogger(__name__)

# Providers yang support tool calling
TOOL_CAPABLE_PROVIDERS = {"groq", "openrouter", "cerebras", "sambanova", "puter"}

def supports_tool_calling(provider_name: str) -> bool:
    return provider_name in TOOL_CAPABLE_PROVIDERS


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
    tool_calls: Any = None
    raw: Any = None

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
        pass
    
    async def health_check(self) -> bool:
        return self.api_key is not None or self.name in ["pollinations", "mlvoca", "puter"]
    
    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


# ============================================================
# OPENAI-COMPATIBLE PROVIDER
# ============================================================

class OpenAICompatibleProvider(BaseProvider):
    """Base class for OpenAI-compatible APIs"""
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AIResponse:
        import time
        start = time.time()
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if kwargs.get("tools"):
            payload["tools"] = kwargs["tools"]
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")
        
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
                        msg = data["choices"][0].get("message", {})
                        content = msg.get("content") or ""
                        tool_calls = msg.get("tool_calls")
                        tokens = data.get("usage", {}).get("total_tokens", 0)
                        
                        return AIResponse(
                            success=True, content=content,
                            provider=self.name, model=model,
                            tokens_used=tokens, latency=latency,
                            tool_calls=tool_calls, raw=data
                        )
                    else:
                        error_text = await resp.text()
                        log.warning(f"{self.name} error {resp.status}: {error_text[:200]}")
                        return AIResponse(
                            success=False, content="",
                            provider=self.name, model=model,
                            error=f"HTTP {resp.status}: {error_text[:100]}",
                            latency=latency
                        )
                        
        except asyncio.TimeoutError:
            return AIResponse(
                success=False, content="", provider=self.name,
                model=model, error="Request timeout"
            )
        except Exception as e:
            log.error(f"{self.name} exception: {e}")
            return AIResponse(
                success=False, content="", provider=self.name,
                model=model, error=str(e)
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
# OPENROUTER PROVIDER (with 404 auto-fallback)
# ============================================================

class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter API - Multi-model gateway with auto-fallback on 404"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.name = "openrouter"
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"
    
    def _build_headers(self) -> Dict[str, str]:
        headers = super()._build_headers()
        headers["HTTP-Referer"] = "https://discord-bot.local"
        headers["X-Title"] = "Discord AI Bot"
        return headers
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AIResponse:
        import time
        start = time.time()
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # Only send tools for supported models
        if kwargs.get("tools"):
            tools_safe = {
                "openrouter/free",
                "qwen/qwen3-coder:free",
                "stepfun/step-3.5-flash:free",
                "qwen/qwen3-next-80b-a3b-instruct:free",
                "nvidia/nemotron-3-nano-30b-a3b:free",
            }
            if model in tools_safe:
                payload["tools"] = kwargs["tools"]
                payload["tool_choice"] = kwargs.get("tool_choice", "auto")
        
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
                        msg = data["choices"][0].get("message", {})
                        content = msg.get("content") or ""
                        tool_calls = msg.get("tool_calls")
                        tokens = data.get("usage", {}).get("total_tokens", 0)
                        
                        return AIResponse(
                            success=True, content=content,
                            provider=self.name, model=model,
                            tokens_used=tokens, latency=latency,
                            tool_calls=tool_calls, raw=data
                        )
                    
                    # 404: Model deprecated → fallback to openrouter/free
                    elif resp.status == 404 and model != "openrouter/free":
                        error_text = await resp.text()
                        log.warning(f"OpenRouter 404 for {model}, fallback to openrouter/free")
                        
                        payload["model"] = "openrouter/free"
                        async with session.post(
                            self.endpoint,
                            headers=self._build_headers(),
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=60)
                        ) as retry:
                            retry_latency = time.time() - start
                            if retry.status == 200:
                                data = await retry.json()
                                msg = data["choices"][0].get("message", {})
                                content = msg.get("content") or ""
                                tokens = data.get("usage", {}).get("total_tokens", 0)
                                return AIResponse(
                                    success=True, content=content,
                                    provider=self.name, model="openrouter/free",
                                    tokens_used=tokens, latency=retry_latency, raw=data
                                )
                            else:
                                return AIResponse(
                                    success=False, content="",
                                    provider=self.name, model=model,
                                    error=f"Fallback failed: HTTP {retry.status}",
                                    latency=retry_latency
                                )
                    
                    # 429: Rate limited
                    elif resp.status == 429:
                        error_text = await resp.text()
                        log.warning(f"OpenRouter 429 for {model}")
                        return AIResponse(
                            success=False, content="",
                            provider=self.name, model=model,
                            error="Rate limited (429). Try again later.",
                            latency=latency
                        )
                    
                    else:
                        error_text = await resp.text()
                        log.warning(f"OpenRouter error {resp.status}: {error_text[:200]}")
                        return AIResponse(
                            success=False, content="",
                            provider=self.name, model=model,
                            error=f"HTTP {resp.status}: {error_text[:100]}",
                            latency=latency
                        )
        
        except asyncio.TimeoutError:
            return AIResponse(
                success=False, content="", provider=self.name,
                model=model, error="Request timeout"
            )
        except Exception as e:
            log.error(f"OpenRouter exception: {e}")
            return AIResponse(
                success=False, content="", provider=self.name,
                model=model, error=str(e)
            )


# ============================================================
# POLLINATIONS PROVIDER
# ============================================================

class PollinationsProvider(OpenAICompatibleProvider):
    """Pollinations API - Free AI gateway"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.name = "pollinations"
        self.endpoint = "https://gen.pollinations.ai/v1/chat/completions"
    
    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    async def health_check(self) -> bool:
        return True


# ============================================================
# CEREBRAS PROVIDER
# ============================================================

class CerebrasProvider(OpenAICompatibleProvider):
    """Cerebras API - Ultra fast inference"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.name = "cerebras"
        self.endpoint = "https://api.cerebras.ai/v1/chat/completions"


# ============================================================
# SAMBANOVA PROVIDER
# ============================================================

class SambanovaProvider(OpenAICompatibleProvider):
    """SambaNova Cloud - Fast inference on RDU hardware"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.name = "sambanova"
        self.endpoint = "https://api.sambanova.ai/v1/chat/completions"


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
        import time
        start = time.time()
        
        cohere_messages = []
        for msg in messages:
            role = "assistant" if msg["role"] == "assistant" else "user"
            if msg["role"] == "system":
                role = "system"
            cohere_messages.append({"role": role, "content": msg["content"]})
        
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
                    self.endpoint, headers=headers, json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    latency = time.time() - start
                    if resp.status == 200:
                        data = await resp.json()
                        content = data["message"]["content"][0]["text"]
                        return AIResponse(
                            success=True, content=content,
                            provider=self.name, model=model, latency=latency
                        )
                    else:
                        return AIResponse(
                            success=False, content="",
                            provider=self.name, model=model,
                            error=f"HTTP {resp.status}", latency=latency
                        )
        except Exception as e:
            return AIResponse(
                success=False, content="",
                provider=self.name, model=model, error=str(e)
            )


# ============================================================
# SILICONFLOW PROVIDER
# ============================================================

class SiliconFlowProvider(OpenAICompatibleProvider):
    """SiliconFlow API - Free tier available
    Default: api.siliconflow.com | China: api.siliconflow.cn"""
    
    def __init__(self, api_key: str, use_china: bool = False):
        super().__init__(api_key)
        self.name = "siliconflow"
        if use_china:
            self.endpoint = "https://api.siliconflow.cn/v1/chat/completions"
        else:
            self.endpoint = "https://api.siliconflow.com/v1/chat/completions"


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
    """Google Gemini API"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.name = "gemini"
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
    
    async def chat(self, messages: List[Dict[str, str]], model: str, temperature: float = 0.7, max_tokens: int = 4096, **kwargs) -> AIResponse:
        import time
        start = time.time()
        
        contents = []
        system_instruction = None
        
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            else:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        
        endpoint = f"{self.base_url}/{model}:generateContent?key={self.api_key}"
        
        payload = {"contents": contents, "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}}
        
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        
        if kwargs.get("search") or kwargs.get("grounding"):
            payload["tools"] = [{"google_search": {}}]
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, headers={"Content-Type": "application/json"}, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    latency = time.time() - start
                    if resp.status == 200:
                        data = await resp.json()
                        content = "".join(part.get("text", "") for part in data["candidates"][0]["content"]["parts"])
                        return AIResponse(success=True, content=content, provider=self.name, model=model, latency=latency)
                    else:
                        error_text = await resp.text()
                        return AIResponse(success=False, content="", provider=self.name, model=model, error=f"HTTP {resp.status}: {error_text[:100]}", latency=latency)
        except Exception as e:
            return AIResponse(success=False, content="", provider=self.name, model=model, error=str(e))


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
        import time
        start = time.time()
        
        endpoint = f"{self.base_url}/{model}"
        payload = {"messages": messages, "max_tokens": max_tokens}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint, headers=headers, json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    latency = time.time() - start
                    if resp.status == 200:
                        data = await resp.json()
                        content = data["result"]["response"]
                        return AIResponse(
                            success=True, content=content,
                            provider=self.name, model=model, latency=latency
                        )
                    else:
                        return AIResponse(
                            success=False, content="",
                            provider=self.name, model=model,
                            error=f"HTTP {resp.status}", latency=latency
                        )
        except Exception as e:
            return AIResponse(
                success=False, content="",
                provider=self.name, model=model, error=str(e)
            )


# ============================================================
# MLVOCA PROVIDER
# ============================================================

class MLVOCAProvider(BaseProvider):
    """MLVOCA API - Free, no key needed"""
    
    def __init__(self):
        super().__init__(None)
        self.name = "mlvoca"
        self.endpoint = "https://mlvoca.com/api/generate"
    
    async def chat(self, messages: List[Dict[str, str]], model: str, **kwargs) -> AIResponse:
        import time
        start = time.time()
        
        prompt = messages[-1]["content"] if messages else ""
        for msg in messages:
            if msg["role"] == "system":
                prompt = f"{msg['content']}\n\n{prompt}"
                break
        
        payload = {"model": model, "prompt": prompt, "stream": False}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint, json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    latency = time.time() - start
                    if resp.status == 200:
                        data = await resp.json()
                        content = data.get("response", "")
                        return AIResponse(
                            success=True, content=content,
                            provider=self.name, model=model, latency=latency
                        )
                    else:
                        return AIResponse(
                            success=False, content="",
                            provider=self.name, model=model,
                            error=f"HTTP {resp.status}", latency=latency
                        )
        except Exception as e:
            return AIResponse(
                success=False, content="",
                provider=self.name, model=model, error=str(e)
            )
    
    async def health_check(self) -> bool:
        return True


# ============================================================
# PUTER PROVIDER
# ============================================================

class PuterProvider(BaseProvider):
    """Puter.com API - Free 200+ AI models"""
    
    def __init__(self, api_token: str = None):
        super().__init__(api_token)
        self.name = "puter"
        self.api_token = api_token
        self.base_url = "https://api.puter.com"
    
    async def chat(self, messages: List[Dict[str, str]], model: str, temperature: float = 0.7, max_tokens: int = 4096, **kwargs) -> AIResponse:
        import time
        start = time.time()
        
        if not self.api_token:
            return AIResponse(success=False, content="", provider=self.name, model=model, error="Puter API token not provided")
        
        # Determine driver - FIXED
        if model.startswith("claude"):
            driver = "claude"
        elif model.startswith("google/") or model.startswith("gemini"):
            driver = "google-vertex"
        elif model.startswith("x-ai/") or model.startswith("grok"):
            driver = "xai"
        elif model.startswith("deepseek"):
            driver = "deepseek"
        elif model.startswith("meta-llama") or model.startswith("llama"):
            driver = "together-ai"
        elif model.startswith("mistral"):
            driver = "mistral"
        elif model.startswith("perplexity"):
            driver = "perplexity"
        elif model.startswith("z-ai/") or model.startswith("glm"):
            driver = "zhipuai"
        else:
            driver = "openai-completion"
        
        payload = {"interface": "puter-chat-completion", "driver": driver, "test_mode": False, "method": "complete", "args": {"messages": messages, "model": model, "stream": False}}
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_token}", "Origin": "https://puter.com"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/drivers/call", headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=90)) as resp:
                    latency = time.time() - start
                    if resp.status == 200:
                        data = await resp.json()
                        try:
                            if "result" in data:
                                result = data["result"]
                                if "message" in result:
                                    content = result["message"].get("content", "")
                                elif "choices" in result:
                                    content = result["choices"][0]["message"]["content"]
                                else:
                                    content = str(result)
                            elif "message" in data:
                                content = data["message"].get("content", str(data))
                            else:
                                content = str(data)
                        except:
                            content = str(data)
                        return AIResponse(success=True, content=content, provider=self.name, model=model, latency=latency)
                    else:
                        error_text = await resp.text()
                        return AIResponse(success=False, content="", provider=self.name, model=model, error=f"HTTP {resp.status}: {error_text[:100]}", latency=latency)
        except asyncio.TimeoutError:
            return AIResponse(success=False, content="", provider=self.name, model=model, error="Request timeout")
        except Exception as e:
            log.error(f"Puter exception: {e}")
            return AIResponse(success=False, content="", provider=self.name, model=model, error=str(e))
    
    async def health_check(self) -> bool:
        return self.api_token is not None


# ============================================================
# PROVIDER FACTORY
# ============================================================

class ProviderFactory:
    """Factory to create provider instances"""
    
    _instances: Dict[str, BaseProvider] = {}
    
    @classmethod
    def get(cls, provider_name: str, api_keys: Dict[str, str]) -> Optional[BaseProvider]:
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
            provider = PollinationsProvider(key)
            
        elif provider_name == "gemini":
            key = api_keys.get("gemini")
            if key:
                provider = GeminiProvider(key)
                
        elif provider_name == "cerebras":
            key = api_keys.get("cerebras")
            if key:
                provider = CerebrasProvider(key)
        
        elif provider_name == "sambanova":
            key = api_keys.get("sambanova")
            if key:
                provider = SambanovaProvider(key)
                
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
        
        elif provider_name == "puter":
            token = api_keys.get("puter_api_key") or api_keys.get("puter")
            if token:
                provider = PuterProvider(token)
        
        if provider:
            cls._instances[provider_name] = provider
        
        return provider
    
    @classmethod
    def clear_cache(cls):
        cls._instances.clear()
