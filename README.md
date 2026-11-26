# Velora — Platformë Inteligjente për Studimin e Studentëve

Velora është një aplikacion web universitar në shqip për organizimin e lëndëve, ruajtjen e materialeve, përmbledhjen me AI, gjenerimin e testeve me nga katër alternativa dhe ruajtjen e rezultateve. Është ndërtuar me Flask, SQLAlchemy dhe PostgreSQL.

## Veçoritë

- Regjistrim, hyrje dhe dalje me fjalëkalime të hash-uara.
- Dashboard responsive në shqip me statistika, si dhe temë e çelët ose e errët.
- Krijim, ndryshim dhe fshirje të lëndëve.
- Materiale me tekst ose PDF; teksti i PDF-së nxirret me `pypdf`. PDF-të e skanuara (pa tekst) nuk mbështeten.
- Përmbledhje me AI, të cilat mund të shihen dhe të fshihen pa prekur materialin origjinal.
- Teste me 3 deri në 15 pyetje nga materiali, me katër alternativa, shpjegim dhe fragment burimor.
- Alternativat përzihen në server, që përgjigjja e saktë të mos qëndrojë gjithmonë në të njëjtin vend.
- Vlerësim automatik, rishikim i përgjigjeve dhe histori rezultatesh.
- Zinxhir shërbimesh AI: kur njëri dështon, kalohet automatikisht te tjetri.
- Mbrojtje CSRF dhe izolim i të dhënave sipas përdoruesit. Sekretet ruhen në `.env`, i cili nuk përfshihet në repository.

## Parakushtet

- Python 3.11 ose më i ri ([python.org/downloads](https://www.python.org/downloads/))
- PostgreSQL ([postgresql.org/download](https://www.postgresql.org/download/))
- Të paktën një shërbim AI: një çelës API ose [Ollama](https://ollama.com/) lokal

## Instalimi (Windows CMD)

Ekzekuto komandat brenda dosjes së projektit:

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

### Databaza

Hap `psql`:

```cmd
psql -U postgres
```

Krijo përdoruesin dhe databazën:

```sql
CREATE USER piss_user WITH PASSWORD 'ndrysho-kete-fjalekalim';
CREATE DATABASE piss_db OWNER piss_user;
\q
```

### Konfigurimi me `.env`

Hap `.env` (i kopjuar nga `.env.example`) dhe plotëso vlerat:

```env
SECRET_KEY=vendos-nje-vlere-te-rastesishme-te-gjate
DATABASE_URL=postgresql+psycopg://piss_user:FJALEKALIMI@localhost:5432/piss_db
AI_PROVIDER=groq,gemini,ollama
GROQ_API_KEY=
GEMINI_API_KEY=
```

Modelet, kufijtë dhe kohët e pritjes janë të shpjeguara në `.env.example`. Mos e shto kurrë `.env` në Git.

Pastaj krijo tabelat:

```cmd
flask --app run.py init-db
```

Databazat e krijuara më herët përditësohen vetë kur nis aplikacioni (shtohet kolona `deleted_at`), nëse përdoruesi i aplikacionit i zotëron tabelat. Nëse tabelat i zotëron `postgres`, ekzekuto një herë:

```cmd
psql -U postgres -d piss_db -c "ALTER TABLE subjects ADD COLUMN IF NOT EXISTS deleted_at timestamptz; ALTER TABLE materials ADD COLUMN IF NOT EXISTS deleted_at timestamptz;"
```

Pas klikimit "Fshi", materiali ose lënda mund të kthehet me "Anulo" për 10 sekonda.

## Nisja

```cmd
flask --app run.py run --debug
```

Hap në browser: `http://127.0.0.1:5000`

Opsioni `--debug` është vetëm për zhvillim lokal.

## Shërbimet AI dhe zinxhiri rezervë

`AI_PROVIDER` pranon një shërbim të vetëm (p.sh. `ollama`) ose një listë të ndarë me presje. Rendi i rekomanduar:

| Rendi | Shërbimi | Variablat në `.env` | Ku merret çelësi |
|---|---|---|---|
| 1 | Groq | `GROQ_API_KEY`, `GROQ_MODEL` | [console.groq.com](https://console.groq.com) |
| 2 | Gemini | `GEMINI_API_KEY`, `GEMINI_MODEL` | [aistudio.google.com](https://aistudio.google.com/apikey) |
| 3 | Ollama (lokal) | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Nuk kërkon çelës |

Mbështeten edhe OpenRouter (`openrouter`), Mistral (`mistral`) dhe Cerebras (`cerebras`) si opsione shtesë. Shërbimet cloud kanë kufij përdorimi që vendosen nga vetë ofruesit.

Si funksionon:

- Shërbimet pa çelës API anashkalohen.
- Kur Groq arrin limitin, pritet pak nëse limiti lirohet shpejt; përndryshe provohet shërbimi tjetër. Me Mistral ose Cerebras në zinxhir kalohet menjëherë te ata.
- Një përmbledhje ose test zgjat më së shumti `AI_TOTAL_TIMEOUT_SECONDS` (90 sekonda); pastaj shfaqet gabim.
- Ollama provohet vetëm kur është i nisur dhe modeli është shkarkuar.
- Kur një shërbim arrin limitin, nuk përgjigjet ose kthen përgjigje të pavlefshme, provohet tjetri.
- Përmbledhja kontrollohet element për element. Elementet bosh, në alfabet tjetër ose pa terma të përbashkët me materialin hiqen. Përsëriten vetëm fushat e domosdoshme që mungojnë, deri në `AI_MAX_ATTEMPTS` herë; arsyet shfaqen në terminal (`AI summary check`). Kontrolli krahason fjalë, jo kuptim, prandaj krahasoje përmbledhjen me materialin.
- Teksti ndahet në pjesë prej `AI_CHUNK_CHARS` (12000) shkronjash, që të bëhen sa më pak thirrje.
- Nëse asnjë përpjekje nuk ka sukses, aplikacioni shfaq gabim dhe nuk ruan asgjë.

Kur përdor shërbimet cloud, teksti i materialit dërgohet te ofruesi përkatës. Për përpunim vetëm lokal vendos `AI_PROVIDER=ollama`.

### Gemini dhe Mistral

Modeli i paracaktuar i Gemini është `gemini-3.5-flash-lite`. Nëse kthen vazhdimisht 503, zgjidh një model tjetër me `GEMINI_MODEL` dhe kontrollo me `flask --app run.py ai-check`.

**Mistral nuk është pjesë e zinxhirit:** qasja në API kërkon pagesë sipas përdorimit (me kartë); pa të, përgjigjet me HTTP 402. Nëse e aktivizon, shto `MISTRAL_API_KEY` te `.env` dhe `mistral` te `AI_PROVIDER`. Kërkesat mund të përdoren për trajnim, përveç nëse e çaktivizon te [admin.mistral.ai](https://admin.mistral.ai).

### Ollama

Për Ollama shkarko modelin:

```cmd
ollama pull gemma3:4b
```

Kontrollo konfigurimin dhe lidhjen (çelësat nuk shfaqen):

```cmd
flask --app run.py ai-check
```

## Testet

Me ambientin virtual aktiv, nga dosja kryesore e projektit:

```cmd
pytest
```

`pytest.ini` i kufizon testet te dosja `tests/`. Testet e aplikacionit përdorin SQLite në memorie dhe nuk kërkojnë PostgreSQL.

## Struktura

```text
app/
  ai/                 Shërbimet AI, zinxhiri rezervë, ndarja e tekstit dhe kontrollet
  ai_service.py       Lidhja e aplikacionit me AI dhe mesazhet e gabimeve
  prompts.py          Udhëzimet për modelet AI
  config.py           Konfigurimi nga environment
  extensions.py       SQLAlchemy, Login Manager, CSRF
  models.py           Modelet e databazës
  main.py             Route-t e aplikacionit
  overview.py         Llogaritjet e panelit dhe ora e Kosovës
  soft_delete.py      Fshirja me mundësi anulimi
  summary_format.py   Formatimi i përmbledhjes dhe blloqet e kodit
  error_pages.py      Faqet e gabimeve
  templates/          UI HTML në shqip
  static/             CSS dhe JavaScript
tests/                Testet
run.py                Entry point Flask
```
