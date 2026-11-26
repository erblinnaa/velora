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
AI_PROVIDER=groq,mistral,gemini,ollama
GROQ_API_KEY=
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
| 2 | Mistral | `MISTRAL_API_KEY`, `MISTRAL_MODEL` | [console.mistral.ai](https://console.mistral.ai) |
| 3 | Gemini | `GEMINI_API_KEY`, `GEMINI_MODEL` | [aistudio.google.com](https://aistudio.google.com/apikey) |
| 4 | Ollama (lokal) | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Nuk kërkon çelës |

Mbështeten edhe OpenRouter (`openrouter`, me `OPENROUTER_API_KEY`) dhe Cerebras (`cerebras`, me `CEREBRAS_API_KEY`; nuk është më falas dhe kërkon kartë) si opsione shtesë. Shërbimet cloud kanë kufij përdorimi që vendosen nga vetë ofruesit.

Si funksionon:

- Shërbimet pa çelës API anashkalohen.
- Kur Groq arrin limitin dhe në zinxhir pas tij ka Mistral (ose Cerebras), kalohet menjëherë te ai. Përndryshe pritet pak, nëse limiti lirohet shpejt.
- Një përmbledhje ose test zgjat më së shumti `AI_TOTAL_TIMEOUT_SECONDS` (90 sekonda); pastaj shfaqet gabim.
- Ollama provohet vetëm kur është i nisur dhe modeli është shkarkuar.
- Kur një shërbim arrin limitin, nuk përgjigjet ose kthen përgjigje të pavlefshme, provohet tjetri.
- Përgjigjja validohet (formati JSON, gjuha dhe mbështetja te materiali). Nëse nuk kalon, kërkesa përsëritet deri në `AI_MAX_ATTEMPTS` herë.
- Nëse asnjë përpjekje nuk ka sukses, aplikacioni shfaq gabim dhe nuk ruan asgjë.

Kur përdor shërbimet cloud, teksti i materialit dërgohet te ofruesi përkatës. Për përpunim vetëm lokal vendos `AI_PROVIDER=ollama`.

### Çelësi i Mistral (falas)

1. Hap [console.mistral.ai](https://console.mistral.ai) dhe hyr ose krijo llogari.
2. Zgjidh planin falas (**Free**), pa kartë.
3. Hap **API Keys**.
4. Krijo çelësin (**New key**), jepi një emër dhe kopjoje menjëherë, sepse shfaqet vetëm një herë.
5. Vendose te `.env`:

```env
MISTRAL_API_KEY=çelësi-yt
AI_PROVIDER=groq,mistral,gemini,ollama
```

6. Rinise aplikacionin dhe kontrollo me `flask --app run.py ai-check`.

Modeli i paracaktuar është `mistral-small-latest`; mund të ndryshohet me `MISTRAL_MODEL`.

**Privatësia:** kërkesat në planin falas mund të përdoren nga Mistral për trajnimin e modeleve, pra edhe teksti i materialeve të tua. Sipas [qendrës së ndihmës](https://help.mistral.ai/en/articles/455207-can-i-opt-out-of-my-input-or-output-data-being-used-for-training), këtë mund ta çaktivizosh te [admin.mistral.ai](https://admin.mistral.ai), menyja **Privacy**.

Kushtet e planit falas ndryshojnë. Në nëntor 2026, [udhëzuesi zyrtar](https://docs.mistral.ai/getting-started/quickstarts/studio/activate-and-generate-api-key) kërkon "një plan me qasje në API" dhe përmend shtimin e metodës së pagesës. Nëse konsola të kërkon kartë ose të bllokon çelësat, ose `ai-check` tregon HTTP 402 për Mistral, plani yt nuk ka qasje në API; kontrollo kushtet para se të vazhdosh.

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
