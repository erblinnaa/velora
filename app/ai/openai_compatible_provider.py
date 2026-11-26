"""Provider for cloud services that speak the OpenAI Chat Completions format.

Groq, Cerebras, Mistral and OpenRouter all expose the same
``POST {base_url}/chat/completions`` endpoint, so a single class covers them.
Only the base URL, the API key and the model name differ.

The standard library is used for HTTP so no new dependency is required.
The API key is never logged and never included in an error message.
"""

import json
import logging
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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


# Known OpenAI-compatible services. The model can always be overridden in .env.
PRESETS = {
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "openai/gpt-oss-120b",
    },
    "cerebras": {
        "label": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "default_model": "gpt-oss-120b",
    },
    "mistral": {
        "label": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-small-latest",
    },
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "google/gemma-3-27b-it:free",
    },
}


class OpenAICompatibleProvider(AIProvider):
    def __init__(
        self,
        name: str,
        api_key: str,
        model: str,
        base_url: str,
        timeout: int = 120,
        label: str | None = None,
        opener=None,
    ):
        self.name = name
        self.label = label or name
        self._api_key = (api_key or "").strip()
        self._model = (model or "").strip()
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = int(timeout)
        # ``opener`` makes the provider testable without real network calls.
        self._opener = opener or urlopen

        env_prefix = name.upper()
        if not self._api_key:
            raise AIProviderConfigurationError(
                f"Çelësi {env_prefix}_API_KEY mungon. Vendose në .env."
            )
        if not self._model:
            raise AIProviderConfigurationError(
                f"{env_prefix}_MODEL mungon. Vendos modelin në .env."
            )
        if not self.base_url:
            raise AIProviderConfigurationError(
                f"Adresa e shërbimit {self.label} mungon."
            )

    @property
    def model(self) -> str:
        return self._model

    # ------------------------------------------------------------------ HTTP
    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Velora/1.0",
            },
            method="POST",
        )

        try:
            with self._opener(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raise self._map_http_error(exc.code) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise AIProviderTimeout(
                f"{self.label} nuk u përgjigj brenda {self.timeout} sekondave."
            ) from exc
        except URLError as exc:
            if isinstance(getattr(exc, "reason", None), (TimeoutError, socket.timeout)):
                raise AIProviderTimeout(
                    f"{self.label} nuk u përgjigj brenda {self.timeout} sekondave."
                ) from exc
            raise AIProviderNetworkError(
                f"Nuk u arrit lidhja me {self.label}. Kontrollo internetin."
            ) from exc
        except OSError as exc:
            raise AIProviderNetworkError(
                f"Nuk u arrit lidhja me {self.label}. Kontrollo internetin."
            ) from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIProviderResponseError(
                f"{self.label} ktheu përgjigje që nuk është JSON."
            ) from exc

    def _map_http_error(self, code: int):
        logger.warning("AI HTTP error: provider=%s status=%s", self.name, code)
        if code in {401, 403}:
            return AIProviderAuthenticationError(
                f"Çelësi API i {self.label} nuk është i vlefshëm."
            )
        if code == 429:
            return AIProviderRateLimitError(
                f"{self.label} arriti limitin falas. Provo më vonë."
            )
        if code == 404:
            return AIProviderModelUnavailable(
                f"Modeli '{self.model}' nuk ekziston te {self.label}."
            )
        if code in {408, 504}:
            return AIProviderTimeout(
                f"{self.label} nuk u përgjigj brenda kohës së lejuar."
            )
        if code >= 500:
            return AIProviderUnavailable(
                f"{self.label} është përkohësisht i padisponueshëm."
            )
        return AIProviderResponseError(
            f"{self.label} refuzoi kërkesën (HTTP {code})."
        )

    # ------------------------------------------------------------ Contract
    @staticmethod
    def _extract_content(response: dict) -> str:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            content = None
        if not isinstance(content, str) or not content.strip():
            raise AIProviderResponseError("AI nuk ktheu përmbajtje të përdorshme.")
        return content.strip()

    @staticmethod
    def _parse_json(content: str):
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].lstrip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Some models add a sentence before or after the JSON object.
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
        raise AIProviderResponseError("AI ktheu JSON të pavlefshëm.")

    def generate_json(self, system_prompt: str, user_prompt: str):
        logger.info("AI request: provider=%s model=%s", self.name, self.model)
        response = self._post(
            "/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 8192,
                "response_format": {"type": "json_object"},
            },
        )
        return self._parse_json(self._extract_content(response))

    def healthcheck(self) -> dict:
        response = self._post(
            "/chat/completions",
            {
                "model": self.model,
                "messages": [{"role": "user", "content": "Përgjigju vetëm me OK."}],
                # Reasoning models spend tokens before answering, so leave room.
                "max_tokens": 256,
            },
        )
        self._extract_content(response)
        return {"provider": self.name, "model": self.model, "available": True}
