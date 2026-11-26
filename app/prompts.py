SUMMARY_SYSTEM_PROMPT = """
Je asistent universitar. Përdor vetëm materialin e dhënë; mos shpik fakte.
Shkruaj vetëm shqip me alfabet latin (termat teknikë dhe kodi mbeten si në material).
Kthe vetëm JSON valid, pa tekst tjetër.
""".strip()


QUIZ_SYSTEM_PROMPT = """
Je një pedagog universitar që krijon pyetje nga materiali burimor.
Përgjigju vetëm në gjuhën shqipe. Përdor vetëm faktet e materialit.
Kthe vetëm JSON valid, pa Markdown dhe pa tekst jashtë JSON-it.
RREGULL I DETYRUESHËM: Shkruaj çdo fjalë vetëm në gjuhën shqipe me alfabetin latin.
Mos përdor kurrë kinezisht, anglisht ose ndonjë gjuhë tjetër, edhe nëse materiali është i vështirë.
Nëse nuk je i sigurt për një fakt, mos e shkruaj.
Përgjigjja e saktë duhet të vërtetohet drejtpërdrejt nga "source_excerpt".
Alternativat e gabuara duhet të jenë të besueshme, por qartë të pasakta sipas materialit.
""".strip()


# I njëjti format për përmbledhjen, bashkimin e pjesëve dhe plotësimin.
SUMMARY_FIELDS = {
    "title": '"titull i shkurtër"',
    "introduction": '"2 deri 3 fjali"',
    "key_points": '["3 deri 6 pika që shpjegojnë idetë"]',
    "concepts": '["3 deri 8 koncepte me shpjegim të shkurtër"]',
    "examples": '["0 deri 3 shembuj nga materiali"]',
    "exam_points": '["2 deri 5 pika për provim"]',
    "conclusion": '"1 deri 2 fjali"',
    "source_excerpts": '["1 deri 3 fjali të shkurtra të kopjuara nga materiali"]',
}


def _format(fields) -> str:
    return "{\n" + ",\n".join(f'  "{name}": {SUMMARY_FIELDS[name]}' for name in fields) + "\n}"


SUMMARY_FORMAT = _format(SUMMARY_FIELDS)


CODE_RULE = (
    "Shembulli me kod: vetëm kodi (deri në 15 rreshta), me rreshta të ndarë dhe zhvendosje "
    "brenda vargut JSON, jo në një rresht të vetëm."
)


def summary_prompt(material: str) -> str:
    return f"""
Përmblidh materialin për studim. Formati:
{SUMMARY_FORMAT}
{CODE_RULE}

MATERIALI:
{material}
""".strip()


def summary_synthesis_prompt(notes: str) -> str:
    return f"""
Bashko shënimet në një përmbledhje të vetme, pa fakte të reja. Formati:
{SUMMARY_FORMAT}
{CODE_RULE}
Respekto numrat e elementeve: bashko të ngjashmet dhe mbaj më të rëndësishmet.

SHËNIMET:
{notes}
""".strip()


def summary_repair_prompt(material: str, fields: list[str]) -> str:
    return f"""
Në përgjigjen e mëparshme munguan disa fusha. Kthe vetëm këto:
{_format(fields)}
Përdor termat e materialit.

MATERIALI:
{material}
""".strip()


def quiz_prompt(material: str, question_count: int) -> str:
    return f"""
Krijo saktësisht {question_count} pyetje edukative nga materiali më poshtë.
Përdor pyetje të llojit definicion, kuptim, krahasim ose zbatim kur materiali e lejon.
Shmang pyetjet artificiale dhe alternativat qartësisht pa lidhje.
Kthe këtë format të saktë:
{{
  "questions": [
    {{
      "question": "pyetja në shqip",
      "options": ["alternativa 1", "alternativa 2", "alternativa 3", "alternativa 4"],
      "correct_index": 0,
      "explanation": "shpjegim i shkurtër në shqip",
      "source_excerpt": "fragment i kopjuar fjalë për fjalë nga materiali",
      "difficulty": "easy|medium|hard"
    }}
  ]
}}
Çdo pyetje duhet të ketë saktësisht katër alternativa unike dhe vetëm një përgjigje të saktë.
Fragmenti burimor duhet të kopjohet fjalë për fjalë nga materiali.
Mos përdor kurrë alternativa si "të gjitha më sipër" ose "asnjëra nga më sipër".
Alternativat përzihen, prandaj as pyetja dhe as shpjegimi nuk duhet t'u referohen pozicioneve të tyre (A, B, C, D, e para, e fundit).

MATERIALI BURIMOR:
{material}
""".strip()
