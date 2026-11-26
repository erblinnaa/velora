"""Chain of AI providers: when one fails or hits its free limit, try the next.

Example order: Groq -> Cerebras -> Mistral -> Gemini -> Ollama (local).
Every provider keeps its own free quota, so together they behave almost like
an unlimited service, and the local model keeps the app working offline.
"""

import logging
import time

from .base import AIProvider
from .deadline import Deadline, run_with_limit
from .errors import AIProviderError, AIProviderRateLimitError, AIProviderUnavailable


logger = logging.getLogger(__name__)

# A rate limited service is worth waiting for only if the wait is short and
# enough time is left afterwards for it to answer.
MAX_RATE_LIMIT_WAIT = 45
TIME_NEEDED_AFTER_WAIT = 10
# Kufiri kryesor mbetet buxheti i kohës; ky numër vetëm ndalon përsëritjet pa fund.
MAX_RATE_LIMIT_WAITS = 8
# Services that answer in seconds. When one of them is still to come in the
# chain, switching to it is quicker than waiting for a rate limit.
QUICK_FALLBACKS = {"cerebras", "mistral"}


class FallbackProvider(AIProvider):
    name = "fallback"

    def __init__(self, providers: list[AIProvider], deadline: Deadline | None = None):
        if not providers:
            raise ValueError("FallbackProvider needs at least one provider.")
        self.providers = list(providers)
        self.deadline = deadline
        self.last_used = None

    @property
    def model(self) -> str:
        return " -> ".join(f"{p.name}:{p.model}" for p in self.providers)

    def generate_json(self, system_prompt: str, user_prompt: str):
        last_error = None
        limited = {}  # rate limited provider -> when it may be tried again
        waits = 0

        for index, provider in enumerate(self.providers):
            self._check_time()
            if not getattr(provider, "ready", lambda: True)():
                continue

            candidate = provider
            while candidate:
                answered, outcome = self._attempt(candidate, system_prompt, user_prompt)
                if answered:
                    return outcome
                last_error = outcome
                if isinstance(outcome, AIProviderRateLimitError) and outcome.retry_after is not None:
                    limited[candidate] = time.monotonic() + outcome.retry_after

                candidate = None
                later = {item.name for item in self.providers[index + 1:]}
                if not later & QUICK_FALLBACKS and waits < MAX_RATE_LIMIT_WAITS:
                    # Before the slow fallbacks, wait for the service that frees up first.
                    candidate = self._wait_for_limit(limited)
                    waits += 1 if candidate else 0

        self._check_time()
        raise last_error or AIProviderUnavailable("Asnjë shërbim AI nuk u përgjigj.")

    def _attempt(self, provider, system_prompt, user_prompt):
        """One call. Returns (True, result) or (False, error)."""
        self._check_time()
        started = time.monotonic()
        try:
            result = self._call(provider, system_prompt, user_prompt)
        except AIProviderError as exc:
            # Rate limit, timeout, network, bad key, invalid JSON ...
            logger.warning(
                "AI provider failed: provider=%s model=%s error=%s seconds=%.1f message=%s",
                provider.name,
                provider.model,
                type(exc).__name__,
                time.monotonic() - started,
                exc,
            )
            return False, exc
        self.last_used = provider.name
        logger.info(
            "AI provider answered: provider=%s seconds=%.1f",
            provider.name,
            time.monotonic() - started,
        )
        return True, result

    def _check_time(self):
        if self.deadline and self.deadline.remaining() <= 0:
            logger.error("AI request stopped: time limit of %ss reached", self.deadline.seconds)
            raise self.deadline.error()

    def _call(self, provider, system_prompt, user_prompt):
        if not self.deadline:
            return provider.generate_json(system_prompt, user_prompt)
        remaining = self.deadline.remaining()
        limit = min(getattr(provider, "timeout", None) or remaining, remaining)
        return run_with_limit(
            lambda: provider.generate_json(system_prompt, user_prompt), limit
        )

    def _wait_for_limit(self, limited: dict):
        """Sleep through the shortest rate limit and return its provider, if worth it."""
        if not self.deadline or not limited:
            return None
        provider = min(limited, key=limited.get)
        wait = round(max(0.0, limited[provider] - time.monotonic()), 1)
        if wait > MAX_RATE_LIMIT_WAIT or self.deadline.remaining() < wait + TIME_NEEDED_AFTER_WAIT:
            return None
        del limited[provider]
        logger.warning(
            "AI rate limit: provider=%s waiting %.0f seconds before trying again",
            provider.name,
            wait + 1,
        )
        time.sleep(wait + 1)
        return provider

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
