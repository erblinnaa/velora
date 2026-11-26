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
AI_PROVIDER=groq,cerebras,mistral,gemini,ollama
GROQ_API_KEY=
CEREBRAS_API_KEY=
MISTRAL_API_KEY=
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
| 2 | Cerebras (provë e kufizuar) | `CEREBRAS_API_KEY`, `CEREBRAS_MODEL` | [cloud.cerebras.ai](https://cloud.cerebras.ai) |
| 3 | Mistral | `MISTRAL_API_KEY`, `MISTRAL_MODEL` | [console.mistral.ai](https://console.mistral.ai) |
| 4 | Gemini | `GEMINI_API_KEY`, `GEMINI_MODEL` | [aistudio.google.com](https://aistudio.google.com/apikey) |
| 5 | Ollama (lokal) | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Nuk kërkon çelës |

Mbështetet edhe OpenRouter (`openrouter`, me `OPENROUTER_API_KEY`) si opsion shtesë. Shërbimet cloud kanë kufij përdorimi që vendosen nga vetë ofruesit.

Si funksionon:

- Shërbimet pa çelës API anashkalohen.
- Kur Groq arrin limitin dhe në zinxhir ka Cerebras ose Mistral, kalohet menjëherë te ata. Përndryshe pritet pak, nëse limiti lirohet shpejt.
- Një përmbledhje ose test zgjat më së shumti `AI_TOTAL_TIMEOUT_SECONDS` (90 sekonda); pastaj shfaqet gabim.
- Ollama provohet vetëm kur është i nisur dhe modeli është shkarkuar.
- Kur një shërbim arrin limitin, nuk përgjigjet ose kthen përgjigje të pavlefshme, provohet tjetri.
- Përgjigjja validohet (formati JSON, gjuha dhe mbështetja te materiali). Nëse nuk kalon, kërkesa përsëritet deri në `AI_MAX_ATTEMPTS` herë.
- Nëse asnjë përpjekje nuk ka sukses, aplikacioni shfaq gabim dhe nuk ruan asgjë.

Kur përdor shërbimet cloud, teksti i materialit dërgohet te ofruesi përkatës. Për përpunim vetëm lokal vendos `AI_PROVIDER=ollama`.

### Çelësi i Cerebras

Sipas [dokumentacionit zyrtar](https://inference-docs.cerebras.ai/support/rate-limits) (nëntor 2026), Cerebras **nuk ka nivel falas të përhershëm**. Llogaritë e reja marrin një provë me kredit prej 5 $ që skadon pas 30 ditësh, dhe për ta aktivizuar [kërkohet një metodë pagese](https://inference-docs.cerebras.ai/console/account-billing). Sipas tyre, pagesë bëhet vetëm nëse blen kredit shtesë; kushtet mund të ndryshojnë, prandaj kontrolloji para regjistrimit.

1. Hap [cloud.cerebras.ai](https://cloud.cerebras.ai) dhe krijo llogari (ose hyr).
2. Shto metodën e pagesës. Pa të, qasja në API mbetet joaktive.
3. Në menynë e majtë zgjidh **API Keys**, pastaj **Generate API Key** dhe jepi një emër.
4. Kopjo çelësin te `.env`:

```env
CEREBRAS_API_KEY=çelësi-yt
CEREBRAS_MODEL=gpt-oss-120b
AI_PROVIDER=groq,cerebras,gemini,ollama
```

5. Rinise aplikacionin dhe kontrollo me `flask --app run.py ai-check`.

Prova ka limit prej 5 kërkesash në minutë për `gpt-oss-120b`. Pa çelës, Cerebras thjesht anashkalohet.

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
  ai/                 Shërbimet AI, zinxhiri rezervë, ndarja e tekstit dhe validimi
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
