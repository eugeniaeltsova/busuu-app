# Busuu Exercise App

Syncs your Busuu vocabulary and grammar progress via the internal API, stores it in PostgreSQL, and generates personalised exercises using Azure OpenAI.

## What it does

1. **Sync** — reads your Busuu session cookies and pulls vocab + grammar data from Busuu's internal API into a PostgreSQL database
2. **Dashboard** — shows all vocabulary items and grammar topics sorted by mastery, so you can see exactly what needs work
3. **Exercises** — generates three types of AI-powered exercises tailored to practice your weakest items:
   - **Short story** — a short narrative using your vocab, with comprehension questions
   - **Translation** — sentences to translate targeting vocabulary
   - **Gap-fill** — a gap text with blanks drawn from grammar topics and vocabulary
4. **Feedback** — submits your answers to the LLM and returns corrections with explanations in your native language

## Project structure

```
busuu-app/
├── run.py                   # entry point: python run.py
├── config.py                # Pydantic settings loaded from .env
├── requirements.txt
│
├── api/
│   ├── main.py              # FastAPI app, lifespan, static files
│   ├── sync.py              # POST /api/sync, GET /api/vocab, GET /api/grammar
│   └── exercises.py         # POST /api/exercise/generate, /feedback, /list
│
├── scraper/
│   ├── busuu_api.py         # HTTP calls to Busuu internal API + data normalisation
│   └── sync_service.py      # upserts user, vocab, grammar into PostgreSQL
│
├── db/
│   ├── models.py            # User, VocabItem, GrammarTopic, Exercise (SQLAlchemy)
│   └── database.py          # async engine + session factory + init_db
│
├── exercises/
│   ├── client.py            # Azure OpenAI client factory
│   ├── utils.py             # pick_vocab, pick_grammar, infer_user_level
│   ├── prompts.py           # all system + user prompt templates
│   ├── tools.py             # function-calling schemas + result parsers
│   ├── agent.py             # calls LLM with the right tool, returns parsed result
│   └── generator.py         # orchestrates generation and feedback, stores Exercise
│
├── frontend/
│   ├── templates/
│   │   ├── index.html       # sync form
│   │   ├── dashboard.html   # vocab + grammar tables
│   │   └── exercises.html   # exercise UI
│   └── static/
│       ├── css/exercises.css
│       └── js/exercises.js  # generate, render, submit, feedback (vanilla JS)
│
└── tests/
    ├── test_utils.py        # pytest — vocab/grammar selection, CEFR inference
    └── test_tools.py        # pytest — exercise parser output
```

## Setup

### 1. Create virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

### 2. Set up the database

The app uses PostgreSQL. The easiest free option is [Supabase](https://supabase.com):

1. Create a free account at supabase.com
2. Click **New project**, set a database password
3. Go to **Settings → Database** and copy the connection string
4. Format it for the app:
```
DATABASE_URL=postgresql+asyncpg://postgres:YOUR-PASSWORD@db.xxxx.supabase.co:5432/postgres

5. Paste it into your `.env` file

The app creates all tables automatically on first startup — no manual migrations needed.

If Supabase asks for a port, use `5432` (direct connection).
If you see a connection refused error, check that you're using the **Direct connection** string, not the pooler.


### 3. Configure environment

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

```dotenv
DATABASE_URL=postgresql+asyncpg://user:password@host:port/dbname
SECRET_KEY=your-secret-key

AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-10-21
```

The app creates tables automatically on first startup via `create_all()`.

### 4. Export Busuu cookies

The app authenticates with Busuu using your browser session cookies — no password is ever stored.

1. Log into [busuu.com](https://busuu.com) in Chrome
2. Install the [Cookie-Editor](https://cookie-editor.com) extension
3. Click **Export → Export as JSON**
4. Save the output to `busuu_cookies.json` in the project root:
   ```bash
   pbpaste > busuu_cookies.json   # macOS
   ```

Cookies expire after ~6 months. Re-export when sync stops working.

### 5. Run the app

```bash
python run.py
```

Open [http://localhost:8000](http://localhost:8000), enter your Busuu email and the path to your cookie file, select your target and native language, and click **Sync**.

## How the sync works

The scraper calls five Busuu internal endpoints using your session cookies:

| Endpoint | Data |
|---|---|
| `GET /users/me` | User profile and native language |
| `GET /vocabulary/all/{lang}` | All vocab items with strength scores (0–5) |
| `GET /api/grammar/progress?language={lang}` | Grammar topic mastery (0–4, percentage) |
| `GET /api/v2/component/grammar_review_{lang}` | Grammar topic names and CEFR levels |
| `GET /api/v2/progress/{lang}` | Full course progress |

All data is upserted (insert or update) so re-syncing is safe.

## How exercises are generated

1. `pick_vocab()` selects words weighted toward weak items (strength 0–1: 50%, medium 2–3: 30%, strong 4–5: 20%)
2. `pick_grammar()` selects topics similarly weighted toward incomplete ones
3. `infer_user_level()` maps completed grammar topics to a CEFR level (A1–C2)
4. The selected vocab and grammar are formatted into a prompt and sent to Azure OpenAI with a function-calling tool schema
5. The model returns a structured response (short story / translation sentences / gap-fill text) that is parsed and stored in the database
6. After submission, your answer is sent to the feedback prompt and corrections are returned

## Supported languages

Spanish, French, German, Russian, Italian, Portuguese, Chinese (Mandarin), Japanese, Arabic, Turkish, Polish

## Running tests

```bash
pytest tests/
```

## Notes on Busuu's internal API

Busuu does not publish a public API. This app calls the same endpoints their web app uses. URL patterns may change when Busuu updates their frontend — if sync stops working, re-export cookies first, then check whether the endpoint paths have changed in `scraper/busuu_api.py`.

**This tool is for personal use only with your own Busuu account.**
