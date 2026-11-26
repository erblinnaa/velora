"""Google Gemini provider implemented with the official google-genai SDK."""

import json
import logging

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from .base import AIProvider
from .errors import (
    AIProviderAuthenticationError,
    AIProviderConfigurationError,
    AIProviderModelUnavailable,
    AIProviderNetworkError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeout,
    AIProviderUnavailable,
)


logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout: int = 120, client=None):
        self._api_key = (api_key or "").strip()
        self._model = (model or "").strip()
        self.timeout = int(timeout)

        if not self._api_key:
            raise AIProviderConfigurationError(
                "Çelësi GEMINI_API_KEY mungon. Vendos një çelës API të Gemini në .env."
            )
        if not self._model:
            raise AIProviderConfigurationError(
                "GEMINI_MODEL mungon. Vendos modelin e Gemini në .env."
            )

        # The SDK expects the timeout in milliseconds. The key is never logged
        # or included in an application error.
        self._client = client or genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(timeout=self.timeout * 1000),
        )

    @property
    def model(self) -> str:
        return self._model

    def _generate(
        self,
        contents: str,
        system_instruction: str | None,
        response_mime_type: str | None,
        max_output_tokens: int | None,
        temperature: float | None = 0.2,
    ):
        logger.info("AI request: provider=%s model=%s", self.name, self.model)
        try:
            config_kwargs = {}
            if temperature is not None:
                config_kwargs["temperature"] = temperature
            if max_output_tokens is not None:
                config_kwargs["max_output_tokens"] = max_output_tokens
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction
            if response_mime_type:
                config_kwargs["response_mime_type"] = response_mime_type

            return self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=(
                    types.GenerateContentConfig(**config_kwargs)
                    if config_kwargs
                    else None
                ),
            )
        except genai_errors.APIError as exc:
            raise self._map_api_error(exc) from exc
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise AIProviderTimeout(
                f"Gemini nuk u përgjigj brenda {self.timeout} sekondave."
            ) from exc
        except (httpx.TransportError, ConnectionError, OSError) as exc:
            raise AIProviderNetworkError(
                "Nuk u arrit lidhja me shërbimin Gemini. Kontrollo rrjetin dhe provo përsëri."
            ) from exc
        except Exception as exc:
            # SDK transport implementations can expose a different concrete
            # exception type. Keep the public message safe and provider-neutral.
            logger.warning(
                "Gemini request failed: provider=%s model=%s error_type=%s",
                self.name,
                self.model,
                type(exc).__name__,
            )
            raise AIProviderUnavailable(
                "Shërbimi Gemini nuk mund të kontaktohej. Provo përsëri më vonë."
            ) from exc

    @staticmethod
    def _map_api_error(exc: genai_errors.APIError):
        code = getattr(exc, "code", None)
        status = str(getattr(exc, "status", "") or "").upper()
        message = str(getattr(exc, "message", "") or "").lower()

        logger.warning("Gemini API error: code=%s status=%s", code, status)

        if code in {401, 403} or (code == 400 and "api key" in message):
            return AIProviderAuthenticationError(
                "Çelësi Gemini API nuk është i vlefshëm ose nuk ka lejet e nevojshme."
            )
        if code == 429:
            return AIProviderRateLimitError(
                "Limiti ose kuota e Gemini API u tejkalua. Provo përsëri më vonë."
            )
        if code == 404:
            return AIProviderModelUnavailable(
                "Modeli i zgjedhur Gemini nuk është i disponueshëm. Kontrollo GEMINI_MODEL."
            )
        if code in {408, 504} or status in {"DEADLINE_EXCEEDED", "TIMEOUT"}:
            return AIProviderTimeout(
                "Gemini nuk u përgjigj brenda kohës së lejuar. Provo me material më të shkurtër."
            )
        if isinstance(code, int) and code >= 500:
            return AIProviderUnavailable(
                "Shërbimi Gemini është përkohësisht i padisponueshëm. Provo përsëri më vonë."
            )
        return AIProviderResponseError(
            "Gemini ktheu një gabim gjatë përpunimit të kërkesës."
        )

    @staticmethod
    def _response_text(response) -> str:
        try:
            text = response.text
        except (AttributeError, ValueError, TypeError) as exc:
            logger.warning("Gemini response validation failed: reason=text_unavailable")
            raise AIProviderResponseError(
                "Gemini nuk ktheu përmbajtje të përdorshme."
            ) from exc

        if not isinstance(text, str) or not text.strip():
            logger.warning("Gemini response validation failed: reason=empty_text")
            raise AIProviderResponseError(
                "Gemini nuk ktheu përmbajtje të përdorshme."
            )
        return text.strip()

    def generate_json(self, system_prompt: str, user_prompt: str):
        response = self._generate(
            contents=user_prompt,
            system_instruction=system_prompt,
            response_mime_type="application/json",
            max_output_tokens=4096,
        )
        content = self._response_text(response)

        # JSON mode normally makes this unnecessary, but accepting a fenced
        # response keeps the parser tolerant of model formatting drift.
        if content.startswith("```") and content.endswith("```"):
            content = content[3:-3].strip()
            if content.lower().startswith("json"):
                content = content[4:].lstrip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning("Gemini response validation failed: reason=invalid_json")
            raise AIProviderResponseError(
                "Gemini ktheu JSON të pavlefshëm."
            ) from exc

    def healthcheck(self) -> dict:
        response = self._generate(
            contents="Përgjigju vetëm me OK.",
            system_instruction=None,
            response_mime_type=None,
            max_output_tokens=None,
            temperature=None,
        )
        self._response_text(response)
        return {
            "provider": self.name,
            "model": self.model,
            "available": True,
        }
