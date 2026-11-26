import io
import json
import time
from urllib.error import HTTPError, URLError

import pytest

from app import ai_service, create_app
from app.ai import factory, fallback_provider
from app.ai.deadline import Deadline
from app.ai.document import has_foreign_script
from app.ai.errors import (
    AIDeadlineExceeded,
    AIOutputValidationError,
    AIProviderAuthenticationError,
    AIProviderConfigurationError,
    AIProviderNetworkError,
    AIProviderRateLimitError,
    AIProviderResponseError,
)
from app.ai.fallback_provider import FallbackProvider
from app.ai.ollama_provider import OllamaProvider
from app.ai.openai_compatible_provider import OpenAICompatibleProvider
from app.ai.service import AIService
from app.prompts import SUMMARY_FORMAT, summary_prompt, summary_synthesis_prompt


MATERIAL = (
    "Python përdoret për ndërtimin e aplikacioneve. Flask është një framework web. "
    "SQLAlchemy menaxhon modelet e bazës së të dhënave. Testimi ndihmon cilësinë e kodit."
)

GOOD_SUMMARY = {
    "title": "Bazat e aplikacioneve web",
    "key_points": [
        "Python përdoret për aplikacione.",
        "Flask është framework web.",
        "SQLAlchemy menaxhon modelet.",
    ],
    "concepts": ["Python", "Flask", "SQLAlchemy"],
    "source_excerpts": ["Flask është një framework web."],
}


# --------------------------------------------------------------- helpers
class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def chat_response(content: str) -> FakeResponse:
    body = {"choices": [{"message": {"content": content}}]}
    return FakeResponse(json.dumps(body).encode("utf-8"))


class RecordingOpener:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def http_error(code: int) -> HTTPError:
    return HTTPError("https://example.test", code, "error", {}, io.BytesIO(b"secret detail"))


def make_provider(opener, **kwargs):
    defaults = dict(
        name="groq",
        label="Groq",
        api_key="test-key-123",
        model="test-model",
        base_url="https://api.example.test/v1",
        opener=opener,
    )
    defaults.update(kwargs)
    return OpenAICompatibleProvider(**defaults)


class ScriptedProvider:
    """Returns or raises the given items in order."""

    def __init__(self, name, items):
        self.name = name
        self.model = f"{name}-model"
        self.items = list(items)
        self.calls = 0

    def generate_json(self, system_prompt, user_prompt):
        self.calls += 1
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def healthcheck(self):
        return {"provider": self.name, "model": self.model, "available": True}


# ------------------------------------------------- OpenAI-compatible provider
def test_openai_compatible_provider_sends_json_request_and_parses_answer():
    opener = RecordingOpener(chat_response(json.dumps({"ok": True})))
    provider = make_provider(opener)

    assert provider.generate_json("sistemi", "përdoruesi") == {"ok": True}

    request = opener.requests[0]
    assert request.full_url == "https://api.example.test/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer test-key-123"
    body = json.loads(request.data.decode("utf-8"))
    assert body["model"] == "test-model"
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0] == {"role": "system", "content": "sistemi"}
    assert body["messages"][1] == {"role": "user", "content": "përdoruesi"}


def test_openai_compatible_provider_accepts_fenced_or_wrapped_json():
    fenced = make_provider(RecordingOpener(chat_response('```json\n{"a": 1}\n```')))
    wrapped = make_provider(RecordingOpener(chat_response('Ja rezultati: {"a": 2} faleminderit')))

    assert fenced.generate_json("s", "u") == {"a": 1}
    assert wrapped.generate_json("s", "u") == {"a": 2}


def test_openai_compatible_provider_rejects_invalid_json():
    provider = make_provider(RecordingOpener(chat_response("jo json fare")))
    with pytest.raises(AIProviderResponseError):
        provider.generate_json("s", "u")


def test_openai_compatible_provider_maps_errors_without_leaking_key():
    limited = make_provider(RecordingOpener(http_error(429)))
    bad_key = make_provider(RecordingOpener(http_error(401)))
    offline = make_provider(RecordingOpener(URLError("no route")))

    with pytest.raises(AIProviderRateLimitError):
        limited.generate_json("s", "u")
    with pytest.raises(AIProviderAuthenticationError) as auth_error:
        bad_key.generate_json("s", "u")
    with pytest.raises(AIProviderNetworkError):
        offline.generate_json("s", "u")

    assert "test-key-123" not in str(auth_error.value)
    assert "secret detail" not in str(auth_error.value)


def test_openai_compatible_provider_requires_api_key():
    with pytest.raises(AIProviderConfigurationError):
        make_provider(RecordingOpener(None), api_key="")


# ---------------------------------------------------------- Fallback chain
def test_fallback_moves_to_next_provider_when_limit_is_reached():
    first = ScriptedProvider("groq", [AIProviderRateLimitError("limit")])
    second = ScriptedProvider("cerebras", [{"ok": True}])
    chain = FallbackProvider([first, second])

    assert chain.generate_json("s", "u") == {"ok": True}
    assert chain.last_used == "cerebras"
    assert first.calls == 1 and second.calls == 1


def test_fallback_raises_last_error_when_every_provider_fails():
    chain = FallbackProvider(
        [
            ScriptedProvider("groq", [AIProviderRateLimitError("limit")]),
            ScriptedProvider("ollama", [AIProviderNetworkError("offline")]),
        ]
    )
    with pytest.raises(AIProviderNetworkError):
        chain.generate_json("s", "u")


# ------------------------------------------------------------------ Factory
def _app(**config):
    base = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "GROQ_API_KEY": "",
        "CEREBRAS_API_KEY": "",
        "MISTRAL_API_KEY": "",
        "OPENROUTER_API_KEY": "",
        "GEMINI_API_KEY": "",
    }
    base.update(config)
    return create_app(base)


def test_factory_builds_chain_and_skips_services_without_key():
    application = _app(
        AI_PROVIDER="groq, cerebras, mistral, ollama",
        GROQ_API_KEY="g-key",
        MISTRAL_API_KEY="m-key",
    )
    with application.app_context():
        provider = factory.create_provider()

    assert isinstance(provider, FallbackProvider)
    assert [p.name for p in provider.providers] == ["groq", "mistral", "ollama"]
    assert provider.providers[0].model == "openai/gpt-oss-120b"


def test_factory_single_cloud_provider_uses_configured_model():
    application = _app(AI_PROVIDER="groq", GROQ_API_KEY="g-key", GROQ_MODEL="llama-3.3-70b-versatile")
    with application.app_context():
        provider = factory.create_provider()

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.model == "llama-3.3-70b-versatile"


def test_factory_chain_without_any_usable_service_fails_clearly():
    application = _app(AI_PROVIDER="groq,cerebras")
    with application.app_context(), pytest.raises(AIProviderConfigurationError):
        factory.create_provider()


# ------------------------------------------------- Albanian-only + retries
def test_foreign_script_is_detected_but_allowed_when_in_source():
    assert has_foreign_script({"text": "Fotosinteza është një proces i 植物"})
    assert not has_foreign_script({"text": "Fotosinteza është proces i bimëve."})
    assert not has_foreign_script({"text": "Fjala Привет"}, source="Përshëndetje: Привет")


def test_service_retries_when_model_drifts_into_another_language():
    drifted = dict(GOOD_SUMMARY, title="Bazat 植物助手")
    provider = ScriptedProvider("ollama", [drifted, GOOD_SUMMARY])

    summary = AIService(provider, max_attempts=3).summarize_material(MATERIAL)

    assert provider.calls == 2
    assert "Bazat e aplikacioneve web" in summary
    assert "植" not in summary


def test_service_gives_up_after_max_attempts():
    drifted = dict(GOOD_SUMMARY, title="Bazat 植物助手")
    provider = ScriptedProvider("ollama", [drifted, drifted])

    with pytest.raises(AIOutputValidationError):
        AIService(provider, max_attempts=2).summarize_material(MATERIAL)
    assert provider.calls == 2


# ------------------------------------------------------------- Time limits
class SlowProvider(ScriptedProvider):
    def __init__(self, name, seconds, timeout=None):
        super().__init__(name, [])
        self.seconds = seconds
        self.timeout = timeout

    def generate_json(self, system_prompt, user_prompt):
        self.calls += 1
        time.sleep(self.seconds)
        return {"slow": True}


def test_slow_provider_is_cut_off_and_the_next_one_answers():
    slow = SlowProvider("gemini", 2, timeout=0.1)
    fast = ScriptedProvider("ollama", [{"ok": True}])
    started = time.monotonic()
    assert FallbackProvider([slow, fast], Deadline(5)).generate_json("s", "u") == {"ok": True}
    assert time.monotonic() - started < 1


def test_whole_request_stops_at_the_deadline_with_albanian_message():
    first = SlowProvider("groq", 2)
    second = ScriptedProvider("gemini", [{"ok": True}])
    started = time.monotonic()
    with pytest.raises(AIDeadlineExceeded, match="brenda 0.2 sekondave"):
        FallbackProvider([first, second], Deadline(0.2)).generate_json("s", "u")
    assert time.monotonic() - started < 1
    assert second.calls == 0


def test_short_rate_limit_is_waited_out_before_falling_back(monkeypatch):
    waited = []
    monkeypatch.setattr(fallback_provider.time, "sleep", waited.append)
    groq = ScriptedProvider("groq", [AIProviderRateLimitError("limit", retry_after=12), {"ok": True}])
    other = ScriptedProvider("gemini", [])
    assert FallbackProvider([groq, other], Deadline(90)).generate_json("s", "u") == {"ok": True}
    assert waited == [13] and other.calls == 0


@pytest.mark.parametrize("retry_after, budget", [(None, 90), (120, 90), (30, 20)])
def test_long_or_unknown_rate_limit_falls_back_at_once(monkeypatch, retry_after, budget):
    waited = []
    monkeypatch.setattr(fallback_provider.time, "sleep", waited.append)
    groq = ScriptedProvider("groq", [AIProviderRateLimitError("limit", retry_after=retry_after)])
    other = ScriptedProvider("gemini", [{"ok": True}])
    assert FallbackProvider([groq, other], Deadline(budget)).generate_json("s", "u") == {"ok": True}
    assert waited == []


def test_rate_limit_error_carries_retry_after_and_logs_reason_without_ids(caplog):
    body = io.BytesIO(json.dumps({"error": {"message": "Limit 8000 for org_abc123"}}).encode())
    error = HTTPError("https://example.test", 429, "error", {"retry-after": "7"}, body)
    with pytest.raises(AIProviderRateLimitError) as raised:
        make_provider(RecordingOpener(error)).generate_json("s", "u")
    assert raised.value.retry_after == 7
    assert "Limit 8000" in caplog.text and "org_abc123" not in caplog.text


@pytest.mark.parametrize("installed, ready", [(["gemma3:4b"], True), (["llama3:latest"], False)])
def test_ollama_is_tried_only_when_its_model_is_pulled(monkeypatch, installed, ready):
    provider = OllamaProvider("http://127.0.0.1:11434", "gemma3:4b")
    monkeypatch.setattr(provider, "_request", lambda *a, **k: {"models": [{"name": n} for n in installed]})
    assert provider.ready() is ready


def test_chain_skips_a_provider_that_is_not_ready():
    missing = ScriptedProvider("ollama", [])
    missing.ready = lambda: False
    groq = ScriptedProvider("groq", [AIProviderRateLimitError("limit")])
    with pytest.raises(AIProviderRateLimitError):
        FallbackProvider([groq, missing]).generate_json("s", "u")
    assert missing.calls == 0


def test_public_service_applies_the_total_limit_to_a_single_provider(monkeypatch):
    slow = SlowProvider("groq", 2)
    monkeypatch.setattr(ai_service, "create_provider", lambda: slow)
    application = _app(AI_PROVIDER="groq", AI_TOTAL_TIMEOUT_SECONDS=0.2)
    with application.app_context(), pytest.raises(ai_service.AIServiceError, match="brenda 0.2 sekondave"):
        ai_service.summarize_material(MATERIAL)


def test_fallbacks_have_short_timeouts():
    application = _app(AI_PROVIDER="groq,gemini", GROQ_API_KEY="g", GEMINI_API_KEY="m", AI_TIMEOUT_SECONDS=120)
    with application.app_context():
        groq, gemini = factory.create_provider().providers
    assert (groq.timeout, gemini.timeout) == (45, 30)


@pytest.mark.parametrize("build", [summary_prompt, summary_synthesis_prompt])
def test_both_summary_prompts_state_the_format_and_its_limits(build):
    prompt = build("tekst prove")
    assert SUMMARY_FORMAT in prompt and "3 deri 6 pika" in prompt
    assert "{{" not in prompt and "tekst prove" in prompt


@pytest.mark.parametrize("fallback", ["cerebras", "mistral"])
def test_rate_limit_switches_to_a_quick_service_without_waiting(monkeypatch, fallback):
    waited = []
    monkeypatch.setattr(fallback_provider.time, "sleep", waited.append)
    groq = ScriptedProvider("groq", [AIProviderRateLimitError("limit", retry_after=5)])
    quick = ScriptedProvider(fallback, [{"ok": True}])
    assert FallbackProvider([groq, quick], Deadline(90)).generate_json("s", "u") == {"ok": True}
    assert waited == []


def test_groq_is_waited_for_when_cerebras_fails_too(monkeypatch):
    waited = []
    monkeypatch.setattr(fallback_provider.time, "sleep", waited.append)
    groq = ScriptedProvider("groq", [AIProviderRateLimitError("limit", retry_after=5), {"ok": True}])
    cerebras = ScriptedProvider("cerebras", [AIProviderNetworkError("offline")])
    gemini = ScriptedProvider("gemini", [])
    chain = FallbackProvider([groq, cerebras, gemini], Deadline(90))
    assert chain.generate_json("s", "u") == {"ok": True}
    assert waited == [6] and gemini.calls == 0


def test_factory_puts_cerebras_second_only_when_it_has_a_key():
    for key, expected in (("c-key", ["groq", "cerebras", "ollama"]), ("", ["groq", "ollama"])):
        application = _app(AI_PROVIDER="groq,cerebras,ollama", GROQ_API_KEY="g", CEREBRAS_API_KEY=key)
        with application.app_context():
            assert [p.name for p in factory.create_provider().providers] == expected

