SUMMARY_SYSTEM_PROMPT = """
Je një asistent universitar që punon vetëm me materialin burimor të dhënë.
Përgjigju vetëm në gjuhën shqipe. Mos përdor njohuri të jashtme dhe mos shpik fakte.
Kthe vetëm JSON valid, pa Markdown dhe pa tekst jashtë JSON-it.
RREGULL I DETYRUESHËM: Shkruaj çdo fjalë vetëm në gjuhën shqipe me alfabetin latin.
Mos përdor kurrë kinezisht, anglisht ose ndonjë gjuhë tjetër, edhe nëse materiali është i vështirë.
Nëse nuk je i sigurt për një fakt, mos e shkruaj.
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


# I njëjti format për përmbledhjen e një pjese dhe për bashkimin e pjesëve.
SUMMARY_FORMAT = """
{
  "title": "titull i shkurtër",
  "introduction": "hyrje e qartë në shqip, 2 deri 4 fjali",
  "key_points": ["3 deri 6 pika të qarta"],
  "concepts": ["3 deri 8 koncepte me shpjegim të shkurtër"],
  "examples": ["1 deri 4 shembuj praktikë vetëm nëse mbështeten nga materiali"],
  "exam_points": ["2 deri 5 pika të rëndësishme për përgatitjen e provimit"],
  "conclusion": "përmbledhje e shkurtër përmbyllëse",
  "source_excerpts": ["1 deri 3 prova të shkurtra të mbështetura në material, si citime ose parafraza"]
}
""".strip()


CODE_RULE = (
    "Kur një shembull është kod programimi, ruaj formatimin e tij brenda vargut JSON: "
    "ndaji rreshtat me \\n dhe ruaj zhvendosjen. Mos e shkruaj kodin në një rresht të vetëm "
    "dhe mos e përziej me shpjegim në të njëjtin element."
)


def summary_prompt(material: str) -> str:
    return f"""
Krijo një përmbledhje edukative nga materiali më poshtë.
Kthe këtë format të saktë:
{SUMMARY_FORMAT}
{CODE_RULE}
Pikat duhet të shpjegojnë idetë, jo vetëm të kopjojnë titujt.
Konceptet duhet të kenë përkufizim ose shpjegim të shkurtër.
Mos shpik shembuj; nëse materiali nuk përmban shembuj praktikë, kthe një listë bosh.
Përfundimi duhet të jetë një rikujtim i shkurtër i ideve kryesore.
Provat burimore duhet të ruajnë termat dhe faktet kryesore të materialit. Ato mund të jenë parafraza të qarta, por mos shto fakte të reja.

MATERIALI BURIMOR:
{material}
""".strip()


def summary_synthesis_prompt(notes: str) -> str:
    return f"""
Bashko shënimet e verifikuara më poshtë në një përmbledhje edukative në shqip.
Mos shto fakte të reja. Kthe këtë format të saktë:
{SUMMARY_FORMAT}
{CODE_RULE}
Numrat e elementeve janë kufij të detyrueshëm: kur shënimet kanë më shumë pika, bashko të ngjashmet dhe mbaj vetëm më të rëndësishmet.
Nëse nuk ka shembuj praktikë, kthe një listë bosh.
source_excerpts duhet të jenë prova të mbështetura qartë nga shënimet e dhëna; nuk është e nevojshme të jenë citime fjalë për fjalë.

SHËNIME TË NXJERRA NGA MATERIALI:
{notes}
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
