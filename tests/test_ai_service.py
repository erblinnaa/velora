import random

import pytest

from app.ai.errors import AIOutputValidationError
from app.ai.service import AIService


class FakeProvider:
    name = "fake"
    model = "test-model"

    def __init__(self, responses):
        self.responses = iter(responses)

    def generate_json(self, system_prompt, user_prompt):
        return next(self.responses)

    def healthcheck(self):
        return {"provider": self.name, "model": self.model, "available": True}


def test_summary_requires_source_evidence():
    material = (
        "Python përdoret për ndërtimin e aplikacioneve. Flask është një framework web. "
        "SQLAlchemy menaxhon modelet e bazës së të dhënave. Testimi ndihmon cilësinë e kodit."
    )
    provider = FakeProvider([
        {
            "title": "Bazat e aplikacioneve web",
            "key_points": ["Python përdoret për aplikacione.", "Flask është framework web.", "SQLAlchemy menaxhon modelet."],
            "concepts": ["Python", "Flask", "SQLAlchemy"],
            "source_excerpts": ["Flask është një framework web."],
        }
    ])

    summary = AIService(provider).summarize_material(material)

    assert "Bazat e aplikacioneve web" in summary
    assert "Flask është një framework web." in summary


def test_summary_parses_richer_albanian_learning_sections():
    material = (
        "Fotosinteza është procesi me të cilin bimët prodhojnë ushqim. "
        "Ajo përdor dritën, ujin dhe dioksidin e karbonit. "
        "Klorofili ndihmon në thithjen e dritës. "
        "Procesi çliron oksigjen në mjedis."
    )
    provider = FakeProvider([
        {
            "title": "Fotosinteza",
            "introduction": "Fotosinteza shpjegon si bimët prodhojnë ushqim duke përdorur dritën.",
            "key_points": ["Bimët prodhojnë ushqim.", "Procesi përdor dritën.", "Oksigjeni çlirohet në mjedis."],
            "concepts": ["Fotosinteza: procesi i prodhimit të ushqimit.", "Klorofili: ndihmon në thithjen e dritës.", "Oksigjeni: çlirohet gjatë procesit."],
            "examples": ["Përdorimi i dritës, ujit dhe dioksidit të karbonit."],
            "exam_points": ["Kushtet e nevojshme për fotosintezën.", "Roli i klorofilit."],
            "conclusion": "Fotosinteza lidh dritën me prodhimin e ushqimit dhe çlirimin e oksigjenit.",
            "source_excerpts": ["Klorofili ndihmon në thithjen e dritës."],
        }
    ])

    summary = AIService(provider).summarize_material(material)

    assert "Hyrje:" in summary
    assert "Shembuj praktikë:" in summary
    assert "Për përgatitjen e provimit:" in summary
    assert "Përfundim:" in summary


def test_summary_accepts_grounded_paraphrased_evidence():
    material = (
        "Fotosinteza është procesi me të cilin bimët prodhojnë ushqim. "
        "Ajo përdor dritën, ujin dhe dioksidin e karbonit. "
        "Klorofili ndihmon në thithjen e dritës. "
        "Procesi çliron oksigjen në mjedis."
    )
    provider = FakeProvider([
        {
            "title": "Fotosinteza",
            "introduction": "Bimët krijojnë ushqim duke përdorur energjinë e dritës.",
            "key_points": [
                "Bimët prodhojnë ushqim.",
                "Procesi përdor dritën dhe ujin.",
                "Gjatë tij çlirohet oksigjen.",
            ],
            "concepts": [
                "Fotosinteza: prodhimi i ushqimit nga bimët.",
                "Klorofili: ndihmon kapjen e dritës.",
                "Oksigjeni: çlirohet në mjedis.",
            ],
            "examples": [],
            "exam_points": [
                "Roli i klorofilit.",
                "Materialet që përdor procesi.",
            ],
            "conclusion": "Fotosinteza lidh dritën me ushqimin dhe oksigjenin.",
            "source_excerpts": [
                "Bimët krijojnë ushqim duke përdorur dritën.",
            ],
        }
    ])

    summary = AIService(provider).summarize_material(material)

    assert "Bimët krijojnë ushqim duke përdorur dritën." in summary


def test_summary_rejects_unsupported_paraphrase():
    material = (
        "Fotosinteza është procesi me të cilin bimët prodhojnë ushqim. "
        "Ajo përdor dritën, ujin dhe dioksidin e karbonit. "
        "Klorofili ndihmon në thithjen e dritës. "
        "Procesi çliron oksigjen në mjedis."
    )
    provider = FakeProvider([
        {
            "title": "Fotosinteza",
            "key_points": ["Bimët prodhojnë ushqim.", "Procesi përdor dritën.", "Çlirohet oksigjen."],
            "concepts": ["Fotosinteza", "Klorofili", "Oksigjeni"],
            "source_excerpts": ["Graviteti përcakton orbitën e planetëve."],
        }
    ])

    with pytest.raises(AIOutputValidationError):
        AIService(provider).summarize_material(material)


def test_summary_rejects_unrelated_claim_even_with_valid_source_evidence():
    material = (
        "Fotosinteza është procesi me të cilin bimët prodhojnë ushqim. "
        "Ajo përdor dritën, ujin dhe dioksidin e karbonit. "
        "Klorofili ndihmon në thithjen e dritës. "
        "Procesi çliron oksigjen në mjedis."
    )
    provider = FakeProvider([
        {
            "title": "Fotosinteza",
            "key_points": [
                "Bimët prodhojnë ushqim.",
                "Procesi përdor dritën.",
                "Universi përbëhet nga galaktika të panumërta.",
            ],
            "concepts": ["Fotosinteza", "Klorofili", "Oksigjeni"],
            "source_excerpts": ["Fotosinteza është procesi me të cilin bimët prodhojnë ushqim."],
        }
    ])

    with pytest.raises(AIOutputValidationError):
        AIService(provider).summarize_material(material)


def test_quiz_requires_four_unique_options_and_source_evidence():
    material = (
        "Python përdoret për ndërtimin e aplikacioneve. Flask është një framework web. "
        "SQLAlchemy menaxhon modelet e bazës së të dhënave. Testimi ndihmon cilësinë e kodit."
    )
    questions = [
        {
            "question": "Çfarë përdoret për ndërtimin e aplikacioneve?",
            "options": ["Python", "Flask", "SQLAlchemy", "Testimi"],
            "correct_index": 0,
            "explanation": "Materiali e thotë drejtpërdrejt këtë.",
            "source_excerpt": "Python përdoret për ndërtimin e aplikacioneve.",
            "difficulty": "easy",
        },
        {
            "question": "Çfarë është Flask?",
            "options": ["Një framework web", "Një bazë të dhënash", "Një test", "Një gjuhë"],
            "correct_index": 0,
            "explanation": "Flask përshkruhet si framework web.",
            "source_excerpt": "Flask është një framework web.",
            "difficulty": "easy",
        },
        {
            "question": "Çfarë menaxhon SQLAlchemy?",
            "options": ["Modelet", "Faqet", "Pyetjet", "Përdoruesit"],
            "correct_index": 0,
            "explanation": "Materiali përmend modelet e bazës së të dhënave.",
            "source_excerpt": "SQLAlchemy menaxhon modelet e bazës së të dhënave.",
            "difficulty": "medium",
        },
    ]
    provider = FakeProvider([{"questions": questions}])

    result = AIService(provider).generate_quiz(material, 3)

    assert len(result) == 3
    assert result[0]["source_excerpt"] in material


def test_quiz_shuffles_options_and_keeps_correct_index_on_right_answer():
    material = (
        "Python përdoret për ndërtimin e aplikacioneve. Flask është një framework web. "
        "SQLAlchemy menaxhon modelet e bazës së të dhënave. Testimi ndihmon cilësinë e kodit."
    )
    # (question, options, position of the right answer, source excerpt)
    cases = [
        (
            "Çfarë përdoret për ndërtimin e aplikacioneve?",
            ["Python", "Flask", "SQLAlchemy", "Testimi"],
            0,
            "Python përdoret për ndërtimin e aplikacioneve.",
        ),
        (
            "Çfarë është Flask?",
            ["Një bazë të dhënash", "Një test", "Një framework web", "Një gjuhë"],
            2,
            "Flask është një framework web.",
        ),
        (
            "Çfarë menaxhon SQLAlchemy?",
            ["Faqet", "Pyetjet", "Përdoruesit", "Modelet"],
            3,
            "SQLAlchemy menaxhon modelet e bazës së të dhënave.",
        ),
    ]
    payload = {
        "questions": [
            {
                "question": question,
                "options": options,
                "correct_index": correct_index,
                "explanation": "Materiali e thotë drejtpërdrejt këtë.",
                "source_excerpt": excerpt,
            }
            for question, options, correct_index, excerpt in cases
        ]
    }
    positions = [set() for _ in cases]

    # A fixed seed makes the many shuffles repeatable.
    random.seed(1234)
    for _ in range(100):
        result = AIService(FakeProvider([payload])).generate_quiz(material, 3)

        for index, (item, case) in enumerate(zip(result, cases)):
            _, options, correct_index, _ = case
            assert sorted(item["options"]) == sorted(options)
            assert item["options"][item["correct_index"]] == options[correct_index]
            positions[index].add(item["correct_index"])

    # The right answer reaches every position, not only the model's original one.
    assert positions == [{0, 1, 2, 3}] * len(cases)


def test_invalid_source_evidence_is_rejected():
    material = (
        "Python përdoret për ndërtimin e aplikacioneve. Flask është një framework web. "
        "SQLAlchemy menaxhon modelet e bazës së të dhënave. Testimi ndihmon cilësinë e kodit."
    )
    provider = FakeProvider([
        {
            "title": "Titull",
            "key_points": ["Një", "Dy", "Tre"],
            "concepts": ["A", "B", "C"],
            "source_excerpts": ["Ky fakt nuk ndodhet në material."],
        }
    ])

    with pytest.raises(AIOutputValidationError):
        AIService(provider).summarize_material(material)
