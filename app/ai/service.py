from dataclasses import dataclass
import logging
import random
import re

from .base import AIProvider
from .document import (
    chunk_text,
    compact_whitespace,
    contains_source_excerpt,
    has_foreign_script,
    is_grounded_in_source,
    normalize_text,
)
from .errors import AIOutputValidationError, AIProviderResponseError
from ..prompts import (
    QUIZ_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
    quiz_prompt,
    summary_prompt,
    summary_synthesis_prompt,
)


logger = logging.getLogger(__name__)


def _summary_validation_error(message: str, rule: str) -> AIOutputValidationError:
    """Log only a safe rule identifier; never log model output or source text."""
    logger.warning("AI summary validation failed: rule=%s", rule)
    return AIOutputValidationError(message)


@dataclass
class AIService:
    provider: AIProvider
    max_input_chars: int = 30000
    chunk_chars: int = 6000
    # How many times one request is tried when the model returns output that
    # fails validation (wrong language, invalid JSON, unsupported facts).
    # The application sets this from AI_MAX_ATTEMPTS (default 3).
    max_attempts: int = 1

    def _generate_validated(self, system_prompt, user_prompt, source, validate):
        """Ask the model, validate the answer and retry on bad output.

        Only output problems are retried here. Provider problems such as
        rate limits are handled by the fallback chain in the factory.
        """
        attempts = max(1, int(self.max_attempts))
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                payload = self.provider.generate_json(system_prompt, user_prompt)
                if has_foreign_script(payload, source):
                    raise AIOutputValidationError(
                        "Modeli u përgjigj në një gjuhë tjetër në vend të shqipes."
                    )
                return validate(payload)
            except (AIOutputValidationError, AIProviderResponseError) as exc:
                logger.warning(
                    "AI output rejected, retrying: attempt=%s/%s error=%s",
                    attempt,
                    attempts,
                    type(exc).__name__,
                )
                last_error = exc
        raise last_error

    def summarize_material(self, content: str) -> str:
        material = normalize_text(content, self.max_input_chars)
        chunks = chunk_text(material, self.chunk_chars)

        partials = [
            self._generate_summary(chunk)
            for chunk in chunks
        ]

        if len(partials) == 1:
            result = partials[0]
        else:
            notes = "\n\n".join(
                f"PJESA {index}:\n{self._summary_as_notes(item)}"
                for index, item in enumerate(partials, start=1)
            )
            result = self._generate_validated(
                SUMMARY_SYSTEM_PROMPT,
                summary_synthesis_prompt(notes),
                material,
                lambda payload: self._validate_summary(payload, material),
            )

        return self._format_summary(result)

    def generate_quiz(self, content: str, question_count: int = 5) -> list[dict]:
        material = normalize_text(content, self.max_input_chars)
        question_count = max(3, min(int(question_count), 15))
        chunks = chunk_text(material, self.chunk_chars)
        groups = self._group_chunks(chunks, min(len(chunks), question_count))
        allocations = self._allocate(question_count, len(groups))

        questions = []
        for group, count in zip(groups, allocations):
            questions.extend(
                self._generate_validated(
                    QUIZ_SYSTEM_PROMPT,
                    quiz_prompt(group, count),
                    group,
                    lambda payload, group=group, count=count: self._validate_questions(
                        payload, group, count
                    ),
                )
            )

        if len(questions) != question_count:
            raise AIOutputValidationError(
                "Modeli nuk krijoi numrin e kërkuar të pyetjeve."
            )

        self._reject_duplicate_questions(questions)
        return [self._shuffle_options(item) for item in questions]

    @staticmethod
    def _shuffle_options(question: dict) -> dict:
        """Reorder the options randomly and move correct_index with the answer.

        Models tend to put the correct answer first, so their order is not kept.
        """
        order = list(range(len(question["options"])))
        random.shuffle(order)
        return {
            **question,
            "options": [question["options"][index] for index in order],
            "correct_index": order.index(question["correct_index"]),
        }

    def _generate_summary(self, material: str) -> dict:
        return self._generate_validated(
            SUMMARY_SYSTEM_PROMPT,
            summary_prompt(material),
            material,
            lambda payload: self._validate_summary(payload, material),
        )

    @staticmethod
    def _summary_as_notes(summary: dict) -> str:
        parts = [
            f"Titulli: {summary['title']}\n"
            f"Pikat: {' | '.join(summary['key_points'])}\n"
            f"Konceptet: {' | '.join(summary['concepts'])}\n"
            f"Fragmente burimore: {' | '.join(summary['source_excerpts'])}"
        ]
        if summary.get("introduction"):
            parts.append(f"Hyrje: {summary['introduction']}")
        if summary.get("examples"):
            parts.append(f"Shembuj: {' | '.join(summary['examples'])}")
        if summary.get("exam_points"):
            parts.append(f"Për provim: {' | '.join(summary['exam_points'])}")
        if summary.get("conclusion"):
            parts.append(f"Përfundim: {summary['conclusion']}")
        return "\n".join(parts)

    @staticmethod
    def _validate_summary(payload: dict, source: str) -> dict:
        if not isinstance(payload, dict):
            raise _summary_validation_error(
                "Përmbledhja e modelit nuk është objekt JSON.", "object_json"
            )

        title = payload.get("title")
        key_points = payload.get("key_points")
        concepts = payload.get("concepts")
        excerpts = payload.get("source_excerpts")
        introduction = payload.get("introduction")
        examples = payload.get("examples")
        exam_points = payload.get("exam_points")
        conclusion = payload.get("conclusion")

        if not isinstance(title, str) or not title.strip():
            raise _summary_validation_error("Përmbledhja nuk ka titull valid.", "title")
        if not isinstance(key_points, list) or not 3 <= len(key_points) <= 6:
            raise _summary_validation_error(
                "Përmbledhja nuk ka pika kryesore valide.", "key_points_shape"
            )
        if not isinstance(concepts, list) or not 3 <= len(concepts) <= 8:
            raise _summary_validation_error(
                "Përmbledhja nuk ka koncepte valide.", "concepts_shape"
            )
        if not isinstance(excerpts, list) or not 1 <= len(excerpts) <= 3:
            raise _summary_validation_error(
                "Përmbledhja nuk ka prova burimore.", "source_excerpts_shape"
            )

        all_items = [*key_points, *concepts, *excerpts]
        if any(not isinstance(item, str) or not item.strip() for item in all_items):
            raise _summary_validation_error(
                "Përmbledhja përmban fusha bosh ose të pavlefshme.",
                "empty_required_item",
            )

        if introduction is not None and (
            not isinstance(introduction, str) or not introduction.strip()
        ):
            raise _summary_validation_error("Përmbledhja nuk ka hyrje të vlefshme.", "introduction")
        if examples is not None and (
            not isinstance(examples, list)
            or len(examples) > 4
            or any(not isinstance(item, str) or not item.strip() for item in examples)
        ):
            raise _summary_validation_error(
                "Shembujt e përmbledhjes nuk janë të vlefshëm.", "examples"
            )
        if exam_points is not None and (
            not isinstance(exam_points, list)
            or not 2 <= len(exam_points) <= 5
            or any(not isinstance(item, str) or not item.strip() for item in exam_points)
        ):
            raise _summary_validation_error(
                "Pikat për provim nuk janë të vlefshme.", "exam_points"
            )
        if conclusion is not None and (
            not isinstance(conclusion, str) or not conclusion.strip()
        ):
            raise _summary_validation_error(
                "Përfundimi i përmbledhjes nuk është i vlefshëm.", "conclusion"
            )

        if any(
            not is_grounded_in_source(
                source,
                excerpt,
                minimum_shared_tokens=2,
                minimum_overlap=0.25,
            )
            for excerpt in excerpts
        ):
            raise _summary_validation_error(
                "Përmbledhja nuk përmban prova të verifikueshme nga materiali.",
                "source_evidence",
            )

        claims = [("title", title)]
        claims.extend(("key_point", item) for item in key_points)
        claims.extend(("concept", item) for item in concepts)
        if introduction:
            claims.append(("introduction", introduction))
        if examples:
            claims.extend(("example", item) for item in examples)
        if exam_points:
            claims.extend(("exam_point", item) for item in exam_points)
        if conclusion:
            claims.append(("conclusion", conclusion))

        for field, claim in claims:
            if not is_grounded_in_source(
                source,
                claim,
                minimum_shared_tokens=1,
                minimum_overlap=0.15,
            ):
                raise _summary_validation_error(
                    "Përmbledhja përmban një pohim që nuk mbështetet nga materiali.",
                    f"claim_grounding:{field}",
                )

        result = {
            "title": title.strip(),
            "key_points": [item.strip() for item in key_points],
            "concepts": [item.strip() for item in concepts],
            "source_excerpts": [item.strip() for item in excerpts],
        }
        if introduction is not None:
            result["introduction"] = introduction.strip()
        if examples is not None:
            result["examples"] = [item.strip() for item in examples]
        if exam_points is not None:
            result["exam_points"] = [item.strip() for item in exam_points]
        if conclusion is not None:
            result["conclusion"] = conclusion.strip()
        return result

    @staticmethod
    def _format_summary(summary: dict) -> str:
        sections = [summary["title"]]
        if summary.get("introduction"):
            sections.append(f"Hyrje:\n{summary['introduction']}")
        sections.append(
            "Pikat kryesore:\n"
            + "\n".join(f"- {item}" for item in summary["key_points"])
        )
        sections.append(
            "Konceptet për t'u mbajtur mend:\n"
            + "\n".join(f"- {item}" for item in summary["concepts"])
        )
        if summary.get("examples"):
            sections.append(
                "Shembuj praktikë:\n"
                + "\n".join(f"- {item}" for item in summary["examples"])
            )
        if summary.get("exam_points"):
            sections.append(
                "Për përgatitjen e provimit:\n"
                + "\n".join(f"- {item}" for item in summary["exam_points"])
            )
        if summary.get("conclusion"):
            sections.append(f"Përfundim:\n{summary['conclusion']}")
        sections.append(
            "Prova nga materiali:\n"
            + "\n".join(f'- "{item}"' for item in summary["source_excerpts"])
        )
        return "\n\n".join(sections)

    @staticmethod
    def _validate_questions(payload: dict, source: str, expected_count: int) -> list[dict]:
        if not isinstance(payload, dict) or not isinstance(payload.get("questions"), list):
            raise AIOutputValidationError("Modeli nuk ktheu listë pyetjesh valide.")

        questions = payload["questions"]
        if len(questions) != expected_count:
            raise AIOutputValidationError(
                "Modeli nuk ktheu numrin e kërkuar të pyetjeve për pjesën e materialit."
            )

        validated = []
        for item in questions:
            if not isinstance(item, dict):
                raise AIOutputValidationError("Një pyetje nuk është objekt JSON.")

            question = item.get("question")
            options = item.get("options")
            correct_index = item.get("correct_index")
            explanation = item.get("explanation")
            source_excerpt = item.get("source_excerpt")
            difficulty = item.get("difficulty", "medium")

            if not isinstance(question, str) or not question.strip():
                raise AIOutputValidationError("Pyetja nuk ka tekst valid.")
            if re.search(r"_{3,}|\.\.\.|plotëso|ploteso", question, re.IGNORECASE):
                raise AIOutputValidationError(
                    "Pyetjet me plotësim bosh nuk lejohen në testet e Velora-s."
                )
            if (
                not isinstance(options, list)
                or len(options) != 4
                or any(not isinstance(option, str) or not option.strip() for option in options)
            ):
                raise AIOutputValidationError("Çdo pyetje duhet të ketë katër alternativa valide.")
            if len({compact_whitespace(option) for option in options}) != 4:
                raise AIOutputValidationError("Alternativat e një pyetjeje duhet të jenë unike.")
            if (
                isinstance(correct_index, bool)
                or not isinstance(correct_index, int)
                or correct_index not in range(4)
            ):
                raise AIOutputValidationError("Indeksi i përgjigjes së saktë nuk është valid.")
            if not isinstance(explanation, str) or not explanation.strip():
                raise AIOutputValidationError("Pyetja nuk ka shpjegim valid.")
            if not isinstance(source_excerpt, str) or not contains_source_excerpt(source, source_excerpt):
                raise AIOutputValidationError(
                    "Pyetja nuk ka fragment burimor të verifikueshëm."
                )
            if difficulty not in {"easy", "medium", "hard"}:
                difficulty = "medium"

            validated.append(
                {
                    "question": question.strip(),
                    "options": [option.strip() for option in options],
                    "correct_index": correct_index,
                    "explanation": explanation.strip(),
                    "source_excerpt": source_excerpt.strip(),
                    "difficulty": difficulty,
                }
            )

        return validated

    @staticmethod
    def _reject_duplicate_questions(questions: list[dict]) -> None:
        fingerprints = [
            re.sub(r"[^\w\s]", "", compact_whitespace(item["question"]))
            for item in questions
        ]
        if len(fingerprints) != len(set(fingerprints)):
            raise AIOutputValidationError("Modeli krijoi pyetje të përsëritura.")

    @staticmethod
    def _allocate(total: int, groups: int) -> list[int]:
        base, remainder = divmod(total, groups)
        return [base + (1 if index < remainder else 0) for index in range(groups)]

    @staticmethod
    def _group_chunks(chunks: list[str], max_groups: int) -> list[str]:
        if len(chunks) <= max_groups:
            return chunks

        groups = [[] for _ in range(max_groups)]
        for index, chunk in enumerate(chunks):
            group_index = min(index * max_groups // len(chunks), max_groups - 1)
            groups[group_index].append(chunk)
        return [" ".join(group) for group in groups if group]
