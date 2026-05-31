"""LLM provider wrappers — unified interface for Anthropic, OpenAI-compatible, and mock."""

import time
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    model: str
    error: str | None = None


class BaseProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_message: str, **kwargs) -> LLMResponse:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


# ── Anthropic ──────────────────────────────────────────────

class AnthropicProvider(BaseProvider):
    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model
        self._name = f"Claude ({model})"

    @property
    def name(self) -> str:
        return self._name

    def generate(self, system_prompt: str, user_message: str, **kwargs) -> LLMResponse:
        try:
            import anthropic
        except ImportError:
            return LLMResponse("", 0, 0, 0, self.model, error="请安装 anthropic 包: pip install anthropic")

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        start = time.time()
        try:
            msg = client.messages.create(
                model=self.model,
                max_tokens=kwargs.get("max_tokens", 1024),
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            elapsed = (time.time() - start) * 1000
            return LLMResponse(
                content=msg.content[0].text,
                latency_ms=elapsed,
                input_tokens=msg.usage.input_tokens,
                output_tokens=msg.usage.output_tokens,
                model=self.model,
            )
        except Exception as e:
            return LLMResponse("", 0, 0, 0, self.model, error=str(e))


# ── OpenAI-compatible (GPT / DeepSeek / GLM / etc.) ────────

class OpenAIProvider(BaseProvider):
    def __init__(self, model: str = "gpt-4o", base_url: str | None = None):
        self.model = model
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self._name = f"OpenAI ({model})"

    @property
    def name(self) -> str:
        return self._name

    def generate(self, system_prompt: str, user_message: str, **kwargs) -> LLMResponse:
        try:
            from openai import OpenAI
        except ImportError:
            return LLMResponse("", 0, 0, 0, self.model, error="请安装 openai 包: pip install openai")

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=self.base_url)
        start = time.time()
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=kwargs.get("max_tokens", 1024),
            )
            elapsed = (time.time() - start) * 1000
            return LLMResponse(
                content=resp.choices[0].message.content or "",
                latency_ms=elapsed,
                input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
                output_tokens=resp.usage.completion_tokens if resp.usage else 0,
                model=self.model,
            )
        except Exception as e:
            return LLMResponse("", 0, 0, 0, self.model, error=str(e))


# ── Mock (demo without API key) ─────────────────────────────

class MockProvider(BaseProvider):
    """返回模拟数据，用于无 API Key 时演示平台功能"""

    def __init__(self, model: str = "mock-v1"):
        self.model = model
        self._name = f"Mock ({model})"

    @property
    def name(self) -> str:
        return self._name

    def generate(self, system_prompt: str, user_message: str, **kwargs) -> LLMResponse:
        import hashlib
        import random

        # 用输入做 seed，同一输入返回相似结果
        seed = int(hashlib.md5(user_message.encode()).hexdigest()[:8], 16)
        random.seed(seed)

        # 模拟延迟
        latency = random.uniform(200, 800)
        input_tokens = len(system_prompt.split()) + len(user_message.split())
        output_tokens = random.randint(50, 200)

        # 模拟回复质量有差异
        styles = [
            f"【Mock 回复】已理解您的需求。针对「{user_message[:30]}...」这个问题，我的回答是：这是一个很好的问题，建议从以下几个方面考虑...",
            f"好的，关于「{user_message[:30]}...」，这里有详细的解答：(1) 首先...(2) 其次...(3) 最后...总结而言，建议采用渐进式方案。",
            f"收到。{user_message[:50]}——简单直接的回答：是的，可以这样做。更详细地说...",
        ]
        content = styles[seed % len(styles)]

        return LLMResponse(
            content=content,
            latency_ms=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model,
        )


# ── Factory ─────────────────────────────────────────────────

def create_provider(provider_type: str, model: str = "", **kwargs) -> BaseProvider:
    providers = {
        "anthropic": lambda: AnthropicProvider(model or "claude-sonnet-4-6"),
        "openai": lambda: OpenAIProvider(model or "gpt-4o", **kwargs),
        "deepseek": lambda: OpenAIProvider(
            model=model or "deepseek-chat",
            base_url="https://api.deepseek.com/v1",
        ),
        "mock": lambda: MockProvider(model or "mock-v1"),
    }
    factory = providers.get(provider_type)
    if not factory:
        raise ValueError(f"Unknown provider: {provider_type}. 可选: {list(providers.keys())}")
    return factory()
