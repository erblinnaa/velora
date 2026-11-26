import json
from types import SimpleNamespace

import pytest

from app import create_app
from app.ai import factory
from app.ai.errors import (
    AIProviderAuthenticationError,
    AIProviderConfigurationError,
    AIProviderRateLimitError,
    AIProviderResponseError,
)
from app.ai.gemini_provider import GeminiProvider
from google.genai import errors as genai_errors


class FakeModels:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response):
        self.models = FakeModels(response)


def test_factory_selects_gemini_without_constructing_ollama(monkeypatch):
    application = create_app(
        {
            "TESTING": True,
            "AI_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-key",
            "GEMINI_MODEL": "gemini-test",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    calls = []

    class FakeGeminiProvider:
        name = "gemini"
        model = "gemini-test"

        def __init__(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(factory, "GeminiProvider", FakeGeminiProvider)
    monkeypatch.setattr(
        factory,
        "OllamaProvider",
        lambda **kwargs: pytest.fail("Ollama must not be constructed for Gemini"),
    )

    with application.app_context():
        provider = factory.create_provider()

    assert provider.name == "gemini"
    assert calls == [
        {"api_key": "test-key", "model": "gemini-test", "timeout": 30}
    ]


def test_gemini_provider_parses_json_and_requests_json_mode():
    payload = {"title": "Titull", "key_points": ["Një"]}
    client = FakeClient(SimpleNamespace(text=json.dumps(payload)))
    provider = GeminiProvider("test-key", "gemini-test", client=client)

    assert provider.generate_json("sistemi", "përdoruesi") == payload
    call = client.models.calls[0]
    assert call["model"] == "gemini-test"
    assert call["contents"] == "përdoruesi"
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].system_instruction == "sistemi"


def test_gemini_provider_rejects_invalid_json():
    provider = GeminiProvider(
        "test-key", "gemini-test", client=FakeClient(SimpleNamespace(text="jo json"))
    )

    with pytest.raises(AIProviderResponseError):
        provider.generate_json("sistemi", "përdoruesi")


def test_gemini_healthcheck_uses_a_minimal_default_request():
    client = FakeClient(SimpleNamespace(text="OK"))
    provider = GeminiProvider("test-key", "gemini-test", client=client)

    assert provider.healthcheck()["available"] is True
    call = client.models.calls[0]
    assert call["contents"] == "Përgjigju vetëm me OK."
    assert call["config"] is None


def test_gemini_provider_maps_api_errors_without_exposing_details():
    invalid_key = genai_errors.ClientError(
        401, {"error": {"message": "private detail"}}
    )
    quota = genai_errors.ClientError(429, {"error": {"message": "private detail"}})

    assert isinstance(
        GeminiProvider._map_api_error(invalid_key), AIProviderAuthenticationError
    )
    assert isinstance(GeminiProvider._map_api_error(quota), AIProviderRateLimitError)
    assert "private detail" not in str(GeminiProvider._map_api_error(invalid_key))


def test_gemini_provider_requires_api_key():
    with pytest.raises(AIProviderConfigurationError):
        GeminiProvider("", "gemini-test")
