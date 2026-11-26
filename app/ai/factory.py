import logging

from flask import current_app

from .errors import AIProviderConfigurationError, AIProviderError
from .fallback_provider import FallbackProvider
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider
from .openai_compatible_provider import PRESETS, OpenAICompatibleProvider


logger = logging.getLogger(__name__)


def provider_names() -> list[str]:
    """Read AI_PROVIDER, which can be one name or a comma separated chain.

    Examples: "ollama", "gemini", "groq,cerebras,mistral,gemini,ollama".
    """
    raw = current_app.config.get("AI_PROVIDER", "ollama") or "ollama"
    names = [part.strip().lower() for part in raw.split(",") if part.strip()]
    return names or ["ollama"]


def _build_single(name: str):
    config = current_app.config
    timeout = config["AI_TIMEOUT_SECONDS"]

    if name == "ollama":
        return OllamaProvider(
            base_url=config["OLLAMA_BASE_URL"],
            model=config["OLLAMA_MODEL"],
            timeout=config.get("OLLAMA_TIMEOUT_SECONDS") or timeout,
        )

    if name == "gemini":
        return GeminiProvider(
            api_key=config.get("GEMINI_API_KEY", ""),
            model=config.get("GEMINI_MODEL", "gemini-3.8-flash"),
            timeout=timeout,
        )

    if name in PRESETS:
        preset = PRESETS[name]
        prefix = name.upper()
        return OpenAICompatibleProvider(
            name=name,
            label=preset["label"],
            api_key=config.get(f"{prefix}_API_KEY", ""),
            model=config.get(f"{prefix}_MODEL") or preset["default_model"],
            base_url=config.get(f"{prefix}_BASE_URL") or preset["base_url"],
            timeout=timeout,
        )

    raise AIProviderConfigurationError(
        f"Provider-i AI '{name}' nuk është i mbështetur."
    )


def create_provider():
    names = provider_names()

    if len(names) == 1:
        return _build_single(names[0])

    providers = []
    for name in names:
        try:
            providers.append(_build_single(name))
        except AIProviderConfigurationError as exc:
            # A provider without an API key is simply skipped in a chain.
            logger.warning("AI provider skipped: provider=%s reason=%s", name, exc)
        except AIProviderError as exc:
            logger.warning("AI provider skipped: provider=%s error=%s", name, type(exc).__name__)

    if not providers:
        raise AIProviderConfigurationError(
            "Asnjë shërbim AI nuk është konfiguruar. Shto të paktën një çelës API "
            "në .env ose përdor Ollama."
        )
    if len(providers) == 1:
        return providers[0]
    return FallbackProvider(providers)
