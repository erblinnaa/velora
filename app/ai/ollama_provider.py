import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .base import AIProvider
from .errors import (
    AIProviderError,
    AIProviderResponseError,
    AIProviderTimeout,
    AIProviderUnavailable,
)


logger = logging.getLogger(__name__)

# Asking the local service which models exist must be quick.
READY_TIMEOUT_SECONDS = 3


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: int = 120):
        self.base_url = base_url.rstrip("/") + "/"
        self._model = model
        self.timeout = timeout

    @property
    def model(self) -> str:
        return self._model

    def _request(self, path: str, payload: dict | None = None, timeout: float | None = None) -> dict:
        url = urljoin(self.base_url, path.lstrip("/"))
        data = None
        headers = {"Accept": "application/json"}

        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url, data=data, headers=headers, method="POST" if data else "GET")

        try:
            with urlopen(request, timeout=timeout or self.timeout) as response:
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

    def _installed_models(self, timeout: float | None = None) -> set[str]:
        response = self._request("/api/tags", timeout=timeout)
        return {
            item.get("name")
            for item in response.get("models", [])
            if isinstance(item, dict) and item.get("name")
        }

    def ready(self) -> bool:
        """False when Ollama is not running or the model has not been pulled."""
        try:
            installed = self._installed_models(READY_TIMEOUT_SECONDS)
        except (AIProviderError, ValueError) as exc:
            logger.warning("Ollama skipped: reason=not_running error=%s", type(exc).__name__)
            return False
        wanted = self.model if ":" in self.model else f"{self.model}:latest"
        if wanted not in installed:
            logger.warning("Ollama skipped: reason=model_not_pulled model=%s", self.model)
            return False
        return True

    def healthcheck(self) -> dict:
        logger.info("AI healthcheck: provider=%s model=%s endpoint=/api/tags", self.name, self.model)
        model_names = self._installed_models()
        return {
            "provider": self.name,
            "model": self.model,
            "available": self.model in model_names,
            "installed_models": sorted(model_names),
        }
