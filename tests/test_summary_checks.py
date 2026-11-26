import json

import pytest

from app.ai.errors import AIOutputValidationError, AIProviderResponseError
from app.ai.service import AIService
from app.ai.summary_checks import check_item
from app.summary_format import parse_summary
from test_ai_chain import GOOD_SUMMARY, MATERIAL, RecordingOpener, chat_response, make_provider


class Recorder:
    name = "fake"
    model = "test-model"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts = []

    def generate_json(self, system_prompt, user_prompt):
        self.prompts.append(user_prompt)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_bad_items_are_removed_without_a_retry_and_the_reasons_are_logged(caplog):
    answer = dict(
        GOOD_SUMMARY,
        key_points=["Flask është framework web.", "", None, "Python përdoret për aplikacione.", "植物助手"],
        examples=["", "Vullkanet shpërthejnë llavë të nxehtë."],
        exam_points=[],
    )
    provider = Recorder(answer)

    summary = AIService(provider, max_attempts=3).summarize_material(MATERIAL)

    assert len(provider.prompts) == 1
    assert "植" not in summary and "Vullkanet" not in summary and "Shembuj" not in summary
    for reason in (
        "item=key_points[1] check=empty",
        "item=key_points[4] check=foreign_language",
        "item=examples[1] check=not_supported shared_terms=0/",
    ):
        assert reason in caplog.text
    assert "Vullkanet" not in caplog.text


def test_retry_asks_only_for_the_missing_field_and_keeps_the_rest():
    first = dict(GOOD_SUMMARY, concepts=["", "Galaktikat rrotullohen ngadalë."])
    provider = Recorder(first, {"concepts": ["Python", "Flask"], "title": "Titull tjetër"})

    summary = AIService(provider, max_attempts=3).summarize_material(MATERIAL)

    repair = provider.prompts[1]
    assert '"concepts"' in repair and '"key_points"' not in repair and '"title"' not in repair
    assert GOOD_SUMMARY["title"] in summary and "Titull tjetër" not in summary
    assert "- Python\n- Flask" in summary


def test_unusable_answer_is_asked_again():
    provider = Recorder(AIProviderResponseError("JSON i pavlefshëm"), GOOD_SUMMARY)
    assert GOOD_SUMMARY["title"] in AIService(provider, max_attempts=2).summarize_material(MATERIAL)
    assert provider.prompts[0] == provider.prompts[1]


def test_answer_made_of_invented_facts_is_still_rejected():
    invented = ["Vullkanet shpërthejnë llavë.", "Galaktikat rrotullohen ngadalë."]
    answer = dict(GOOD_SUMMARY, key_points=invented)
    with pytest.raises(AIOutputValidationError, match="key_points"):
        AIService(Recorder(answer, answer), max_attempts=2).summarize_material(MATERIAL)


@pytest.mark.parametrize("claim", [
    "Studentët duhet të kuptojnë rëndësinë e testimit për cilësinë.",
    "Modelet e bazes se te dhenave menaxhohen me SQLAlchemy.",
])
def test_differently_worded_points_are_accepted(claim):
    assert check_item("key_points", claim, MATERIAL) is None


def test_short_declarations_with_literal_backslash_n_become_a_code_block():
    summary = AIService._format_summary(dict(GOOD_SUMMARY, examples=[r"int numri;\ndouble shuma;"]))
    assert ("code", "int numri;\ndouble shuma;") in parse_summary(summary)


def test_code_with_literal_backslash_n_gets_real_lines_but_strings_stay():
    code = r'int x = 1;\nSystem.out.print("a\nb");'
    summary = AIService._format_summary(dict(GOOD_SUMMARY, examples=[code]))
    assert ("code", 'int x = 1;\nSystem.out.print("a\\nb");') in parse_summary(summary)


@pytest.mark.parametrize("model, effort", [("openai/gpt-oss-120b", "low"), ("test-model", None)])
def test_request_limits_output_tokens(model, effort):
    opener = RecordingOpener(chat_response(json.dumps({"ok": True})))
    make_provider(opener, model=model).generate_json("s", "u")
    body = json.loads(opener.requests[0].data)
    assert body["max_tokens"] == 4096 and body.get("reasoning_effort") == effort
