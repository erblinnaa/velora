import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .base import AIProvider
from .errors import (
    AIProviderResponseError,
    AIProviderTimeout,
    AIProviderUnavailable,
)


logger = logging.getLogger(__name__)


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: int = 120):
        self.base_url = base_url.rstrip("/") + "/"
        self._model = model
        self.timeout = timeout

    @property
    def model(self) -> str:
        return self._model

    def _request(self, path: str, payload: dict | None = None) -> dict:
        url = urljoin(self.base_url, path.lstrip("/"))
        data = None
        headers = {"Accept": "application/json"}

        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url, data=data, headers=headers, method="POST" if data else "GET")

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise AIProviderUnavailable(
                f"Ollama ktheu HTTP {exc.code}: {detail}"
            ) from exc
        except TimeoutError as exc:
            raise AIProviderTimeout(
                f"Ollama nuk u përgjigj brenda {self.timeout} sekondave."
            ) from exc
        except URLError as exc:
            raise AIProviderUnavailable(
                "Ollama nuk është i disponueshëm. Nis shërbimin lokal dhe kontrollo URL-në."
            ) from exc
        except OSError as exc:
            raise AIProviderUnavailable(
                "Nuk u arrit lidhja me shërbimin lokal Ollama."
            ) from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIProviderResponseError(
                "Ollama ktheu përgjigje që nuk është JSON valide."
            ) from exc

    def generate_json(self, system_prompt: str, user_prompt: str):
        logger.info("AI request: provider=%s model=%s endpoint=/api/chat", self.name, self.model)
        response = self._request(
            "/api/chat",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
            },
        )

        message = response.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise AIProviderResponseError(
                "Ollama nuk ktheu përmbajtje të përdorshme."
            )

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise AIProviderResponseError(
                "Modeli lokal ktheu JSON të pavlefshëm."
            ) from exc

    def healthcheck(self) -> dict:
        logger.info("AI healthcheck: provider=%s model=%s endpoint=/api/tags", self.name, self.model)
        response = self._request("/api/tags")
        models = response.get("models", [])
        model_names = {
            item.get("name")
            for item in models
            if isinstance(item, dict) and item.get("name")
        }
        return {
            "provider": self.name,
            "model": self.model,
            "available": self.model in model_names,
            "installed_models": sorted(model_names),
        }
