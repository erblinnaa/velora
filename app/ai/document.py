import re
import unicodedata

from .errors import AIOutputValidationError


ALBANIAN_STOPWORDS = {
    "a", "ai", "ajo", "ata", "ato", "as", "dhe", "do", "duke", "edhe",
    "është", "janë", "i", "ia", "jo", "kjo", "ky", "më", "me", "nga",
    "në", "nëpër", "nuk", "ose", "pa", "për", "që", "se", "si", "së",
    "të", "ta", "te", "ti", "u", "veç", "vetëm", "ësaj", "është", "një",
}


def normalize_text(content: str, max_chars: int = 30000) -> str:
    if not isinstance(content, str) or not content.strip():
        raise AIOutputValidationError(
            "Materiali është bosh. Shto tekst para se të vazhdosh."
        )

    text = re.sub(r"\s+", " ", content).strip()
    if len(text) < 80:
        raise AIOutputValidationError(
            "Materiali është shumë i shkurtër për përpunim edukativ."
        )

    return text[:max_chars]


def chunk_text(content: str, max_chars: int = 6000) -> list[str]:
    """Split text on sentence boundaries while preserving source text."""
    sentences = re.split(r"(?<=[.!?])\s+", content.strip())
    chunks = []
    current = []
    current_length = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if current and current_length + len(sentence) + 1 > max_chars:
            chunks.append(" ".join(current))
            current = []
            current_length = 0

        current.append(sentence)
        current_length += len(sentence) + 1

    if current:
        chunks.append(" ".join(current))

    return chunks or [content.strip()]


def compact_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().casefold()


def contains_source_excerpt(material: str, excerpt: str) -> bool:
    excerpt_text = compact_whitespace(excerpt)
    material_text = compact_whitespace(material)
    return bool(excerpt_text) and excerpt_text in material_text


def _content_tokens(value: str) -> set[str]:
    tokens = re.findall(r"[^\W\d_]+", (value or "").casefold(), flags=re.UNICODE)
    return {
        token
        for token in tokens
        if len(token) > 2 and token not in ALBANIAN_STOPWORDS
    }


# Words a summary uses to talk about studying. They say nothing about the facts,
# so they do not count against a point that is worded differently.
_STUDY_WORDS = (
    "përmbledhje material student koncept kupto kujto njoh dalloni shpjego "
    "rëndësi rol përdorim mënyrë bazë kryesor pika provim tema ligjërata prezanton "
    "përfshirë përfshijnë duhet mund llojet"
)


def _stem(token: str) -> str:
    """A short stem without diacritics, to tolerate Albanian inflections."""
    plain = unicodedata.normalize("NFKD", token)
    return "".join(c for c in plain if not unicodedata.combining(c))[:5]


_STOP_STEMS = {_stem(word) for word in ALBANIAN_STOPWORDS}
_STUDY_STEMS = {_stem(word) for word in _STUDY_WORDS.split()}


def _stems(value: str) -> set[str]:
    return {_stem(token) for token in _content_tokens(value)} - _STOP_STEMS


def grounding_score(material: str, candidate: str) -> tuple[int, int]:
    """(key terms of ``candidate`` found in ``material``, all its key terms).

    This compares words, not meaning: it removes text about other subjects,
    but not a false sentence built from the material's own words. An exact
    quote always scores full marks.
    """
    source = _stems(material)
    terms = _stems(candidate)
    if contains_source_excerpt(material, candidate):
        return max(len(terms), 2), max(len(terms), 2)
    terms -= _STUDY_STEMS - source
    return len(terms & source), len(terms)


# Scripts that never appear in normal Albanian text. Small local models
# sometimes drift into Chinese (or another script) in the middle of an answer.
_FOREIGN_SCRIPT_RANGES = (
    (0x0400, 0x04FF),  # Cyrillic
    (0x0600, 0x06FF),  # Arabic
    (0x0E00, 0x0E7F),  # Thai
    (0x3040, 0x30FF),  # Japanese Hiragana / Katakana
    (0x3400, 0x4DBF),  # CJK Extension A
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs (Chinese)
    (0xAC00, 0xD7AF),  # Korean Hangul
    (0xFF00, 0xFFEF),  # Full-width forms
)


def _is_foreign_char(char: str) -> bool:
    code = ord(char)
    return any(start <= code <= end for start, end in _FOREIGN_SCRIPT_RANGES)


def iter_strings(value):
    """Yield every string inside a nested JSON-like structure."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from iter_strings(item)


def has_foreign_script(payload, source: str = "") -> bool:
    """True when the model output contains a non-Albanian script.

    Characters that also appear in the source material are allowed, so a
    material that legitimately quotes another alphabet is not rejected.
    """
    allowed = {char for char in source if _is_foreign_char(char)}
    for text in iter_strings(payload):
        for char in text:
            if _is_foreign_char(char) and char not in allowed:
                return True
    return False
