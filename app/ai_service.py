
from flask import current_app

from .ai.errors import (
    AIOutputValidationError,
    AIProviderAuthenticationError,
    AIProviderConfigurationError,
    AIProviderModelUnavailable,
    AIProviderNetworkError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeout,
    AIProviderUnavailable,
)
from .ai.factory import create_provider, provider_names
from .ai.service import AIService


class AIServiceError(Exception):
    """Public application-level error for AI generation failures."""


def _service():
    return AIService(
        provider=create_provider(),
        max_input_chars=current_app.config["AI_MAX_INPUT_CHARS"],
        chunk_chars=current_app.config["AI_CHUNK_CHARS"],
        max_attempts=current_app.config.get("AI_MAX_ATTEMPTS", 3),
    )


def _raise_public_error(exc):
    names = provider_names()
    only_local = names == ["ollama"]
    is_chain = len(names) > 1

    if isinstance(exc, AIProviderConfigurationError):
        message = str(exc)
    elif isinstance(exc, AIProviderAuthenticationError):
        message = "Çelësi API i shërbimit AI nuk është i vlefshëm. Kontrollo .env."
    elif isinstance(exc, AIProviderRateLimitError):
        message = (
            "Të gjitha shërbimet AI arritën limitin falas për momentin. Provo përsëri më vonë."
            if is_chain
            else "Shërbimi AI arriti limitin falas. Provo përsëri më vonë."
        )
    elif isinstance(exc, AIProviderModelUnavailable):
        message = "Modeli AI i zgjedhur nuk është i disponueshëm. Kontrollo emrin e modelit në .env."
    elif isinstance(exc, AIProviderNetworkError):
        message = "Nuk u arrit lidhja me shërbimin AI. Kontrollo internetin dhe provo përsëri."
    elif isinstance(exc, AIProviderTimeout):
        message = (
            "Shërbimi lokal AI nuk është i disponueshëm. Kontrollo që Ollama të jetë nisur."
            if only_local
            else "Gjenerimi AI tejkaloi kohën e lejuar. Provo me material më të shkurtër."
        )
    elif isinstance(exc, AIOutputValidationError):
        message = (
            "Përgjigjja e AI nuk mund të validohej kundrejt materialit. "
            "Asnjë rezultat nuk u ruajt."
        )
    elif isinstance(exc, AIProviderResponseError):
        message = "AI ktheu një përgjigje të pavlefshme. Provo përsëri."
    elif isinstance(exc, AIProviderUnavailable) and only_local:
        message = (
            "Shërbimi lokal AI nuk është i disponueshëm. "
            "Kontrollo që Ollama të jetë nisur dhe modeli të jetë i instaluar."
        )
    else:
        message = "Shërbimi AI nuk mund të kontaktohej. Provo përsëri më vonë."
    raise AIServiceError(message) from exc


def summarize_material(content):
    try:
        return _service().summarize_material(content)
    except AIProviderError as exc:
        _raise_public_error(exc)


def generate_quiz(content, question_count=5):
    try:
        return _service().generate_quiz(content, question_count)
    except AIProviderError as exc:
        _raise_public_error(exc)
