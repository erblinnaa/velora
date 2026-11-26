"""Kontrollet e përmbledhjes, element për element.

Një element bosh, në gjuhë tjetër ose pa mbështetje te materiali hiqet vetë;
pjesa tjetër e përgjigjes mbahet. Vetëm fushat e domosdoshme që mbeten bosh
kërkohen përsëri nga modeli.
"""

from dataclasses import dataclass

from .document import grounding_score, has_foreign_script


TEXT_FIELDS = ("title", "introduction", "conclusion")
# Fusha -> sa elemente mbahen më së shumti.
LIST_FIELDS = {
    "key_points": 6,
    "concepts": 8,
    "examples": 4,
    "exam_points": 5,
    "source_excerpts": 3,
}
FIELDS = (
    "title", "introduction", "key_points", "concepts",
    "examples", "exam_points", "conclusion", "source_excerpts",
)
# Pa këto përmbledhja nuk ka vlerë: fusha -> sa elemente duhen të paktën.
REQUIRED = {"title": 1, "key_points": 2, "concepts": 2, "source_excerpts": 1}

# Pjesa e termave kyç të një elementi që duhet të gjendet te materiali.
MINIMUM_OVERLAP = 0.25
# Provat burimore duhet të ndajnë të paktën dy terma me materialin.
MINIMUM_EXCERPT_TERMS = 2


@dataclass(frozen=True)
class Rejection:
    """Pse u hoq diçka. Nuk përmban tekst të modelit ose të materialit."""

    item: str
    check: str
    detail: str = ""

    def __str__(self):
        return f"item={self.item} check={self.check}" + (f" {self.detail}" if self.detail else "")


def check_item(field: str, value, source: str) -> tuple[str, str] | None:
    """None kur elementi pranohet, përndryshe (kontrolli, shpjegimi)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return "empty", ""
    if not isinstance(value, str):
        return "not_text", f"type={type(value).__name__}"
    if has_foreign_script(value, source):
        return "foreign_language", ""

    shared, total = grounding_score(source, value)
    needed = MINIMUM_EXCERPT_TERMS if field == "source_excerpts" else 1
    if shared < min(needed, total or needed) or shared < MINIMUM_OVERLAP * total:
        return "not_supported", f"shared_terms={shared}/{total}"
    return None


def clean_summary(payload, source: str, fields=FIELDS) -> tuple[dict, list[Rejection]]:
    """Mban vetëm elementet e pranuara nga fushat e kërkuara."""
    if not isinstance(payload, dict):
        return {}, [Rejection("answer", "not_json_object")]

    kept, rejections = {}, []
    for field in fields:
        value = payload.get(field)
        if field in TEXT_FIELDS:
            problem = check_item(field, value, source)
            if problem is None:
                kept[field] = value.strip()
            elif value is not None or field in REQUIRED:
                rejections.append(Rejection(field, *problem))
            continue

        if not isinstance(value, list):
            if value is not None or field in REQUIRED:
                rejections.append(Rejection(field, "not_a_list"))
            continue

        items = []
        for index, item in enumerate(value):
            problem = check_item(field, item, source)
            if problem:
                rejections.append(Rejection(f"{field}[{index}]", *problem))
            else:
                items.append(item.strip())
        if items:
            kept[field] = items[: LIST_FIELDS[field]]
    return kept, rejections


def merge_summary(collected: dict, new: dict) -> None:
    """Shton te `collected` atë që solli përgjigjja e re, pa përsëritje."""
    for field, value in new.items():
        if field in TEXT_FIELDS:
            collected.setdefault(field, value)
        else:
            items = collected.get(field, [])
            items = items + [item for item in value if item not in items]
            collected[field] = items[: LIST_FIELDS[field]]


def missing_fields(collected: dict) -> list[str]:
    missing = []
    for field, minimum in REQUIRED.items():
        value = collected.get(field)
        count = len(value) if isinstance(value, list) else int(bool(value))
        if count < minimum:
            missing.append(field)
    return missing
