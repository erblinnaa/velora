"""Chain of AI providers: when one fails or hits its free limit, try the next.

Example order: Groq -> Cerebras -> Mistral -> Gemini -> Ollama (local).
Every provider keeps its own free quota, so together they behave almost like
an unlimited service, and the local model keeps the app working offline.
"""

import logging

from .base import AIProvider
from .errors import AIProviderError, AIProviderUnavailable


logger = logging.getLogger(__name__)


class FallbackProvider(AIProvider):
    name = "fallback"

    def __init__(self, providers: list[AIProvider]):
        if not providers:
            raise ValueError("FallbackProvider needs at least one provider.")
        self.providers = list(providers)
        self.last_used = None

    @property
    def model(self) -> str:
        return " -> ".join(f"{p.name}:{p.model}" for p in self.providers)

    def generate_json(self, system_prompt: str, user_prompt: str):
        last_error = None
        for provider in self.providers:
            try:
                result = provider.generate_json(system_prompt, user_prompt)
            except AIProviderError as exc:
                # Rate limit, timeout, network, bad key, invalid JSON ...
                # Any provider failure moves on to the next one.
                logger.warning(
                    "AI provider failed, trying next: provider=%s error=%s",
                    provider.name,
                    type(exc).__name__,
                )
                last_error = exc
                continue
            self.last_used = provider.name
            return result

        raise last_error or AIProviderUnavailable("Asnjë shërbim AI nuk u përgjigj.")

    def healthcheck(self) -> dict:
        results = []
        for provider in self.providers:
            try:
                status = provider.healthcheck()
            except AIProviderError as exc:
                status = {
                    "provider": provider.name,
                    "model": provider.model,
                    "available": False,
                    "error": str(exc),
                }
            results.append(status)
        return {
            "provider": self.name,
            "model": self.model,
            "available": any(item.get("available") for item in results),
            "providers": results,
        }
