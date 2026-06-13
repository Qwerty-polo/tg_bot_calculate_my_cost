# 🤖 Expense Tracker — Telegram Bot

A minimal Telegram bot for **personal expense tracking from banking
screenshots**. Send a screenshot from Monobank, Privat24, A‑Bank (or any
banking app) and the bot will:

1. **OCR** the image to extract the raw transaction text.
2. **Understand** the transactions with **Google Gemini** and turn them into
   structured records (amount, time, merchant).
3. **Skip incoming money** — top-ups, transfers received, cashback, salary and
   pensions are never counted as expenses.
4. **Track budgets** (weekly / monthly) and show simple spending totals.

> 💱 **Currency:** the bot is **UAH-only**. Every amount is stored and shown in
> Ukrainian hryvnia (₴), regardless of what currency a screenshot shows.

Built with **aiogram 3**, **SQLAlchemy 2 (async)**, **Alembic**, **Google
Gemini** (via its OpenAI-compatible API) and **pytesseract/easyocr**. Fully
asynchronous, Python 3.12+, Docker-ready.

---

## ✨ Features

- 📷 **Screenshot analysis** — OCR + AI extraction of each expense
  (amount, time, merchant).
- 🚫 **Incoming money ignored** — top-ups, transfers received, cashback,
  salary/pension are skipped both by the AI prompt and a DB-layer safety filter.
- 🎯 **Budget planning** — `/set_week_budget`, `/set_month_budget`.
- 📅 **Today's expenses** — `/today` (time — merchant — amount).
- 📊 **Simple statistics** — `/stats`: totals for today / week / month and the
  remaining weekly & monthly budget. No charts, no AI insights, no categories.
- 🗑 **Reset Statistics** — a main-menu button to wipe all your own expenses
  and budgets (per-user, with a confirmation step).

---

## 🗂️ Project structure

```
app/
├── main.py            # entrypoint (long-polling)
├── bot/               # Bot + Dispatcher factories, command menu
├── config/            # pydantic-settings configuration (.env)
├── handlers/          # aiogram routers: common, reset, screenshots, budgets, stats
├── services/          # DB business logic: user / expense / budget services
├── database/          # async engine, session, declarative base
├── models/            # SQLAlchemy models + enums
├── ai/                # Gemini client, prompt, parsing & income filter
├── ocr/               # OCR service (tesseract / easyocr)
├── middlewares/       # logging + session/services injection
└── utils/             # formatting, timeframes, logging config
alembic/               # database migrations
tests/                 # unit tests (parsing, income filter, formatting)
scripts/smoke_test.py  # end-to-end pipeline smoke test (no Telegram needed)
```

---

## 🗄️ Database schema

SQLite (MVP) via async SQLAlchemy; migrations managed by Alembic.

| Table       | Key columns |
|-------------|-------------|
| **users**   | `id`, `telegram_id` (unique), `username`, `full_name`, `currency`, `created_at` |
| **expenses**| `id`, `user_id → users.id`, `amount`, `currency`, `occurred_at`, `merchant`, `raw_text`, `created_at` |
| **budgets** | `id`, `user_id → users.id`, `period` (week/month), `amount`, `currency`, `created_at` — unique per (user, period) |

---

## ⚙️ How OCR + AI processing works

```
Screenshot (photo)
   │  message.bot.download()
   ▼
OCR (app/ocr)            tesseract or easyocr, with light preprocessing
   │  raw text
   ▼
AI parsing (app/ai)      Gemini chat completion, response_format=json_object
   │  validated with Pydantic (app/ai/schemas.ParsedExpense)
   ▼
Persistence (services)   ExpenseService.add_many() — rejects incoming money
   │
   ▼
Formatting (utils)       simple expense list + totals → message text
```

**Gemini via the OpenAI SDK:** Gemini is the only LLM provider. It is called
through the `openai` Python SDK pointed at Google's OpenAI-compatible endpoint
(`https://generativelanguage.googleapis.com/v1beta/openai/`), so the `openai`
package is used purely as the HTTP client.

**Graceful degradation:** if `GEMINI_API_KEY` is not set, transaction parsing
falls back to a regex heuristic parser (which also skips incoming-money lines).

OCR runs in a worker thread (`asyncio.to_thread`) so the event loop is never
blocked.

### Example AI prompts

The exact prompts live in [`app/ai/prompts.py`](app/ai/prompts.py). In short:

**Transaction extraction (system):**

> You are a meticulous financial data extraction engine… You receive raw OCR
> text from Ukrainian banking apps… Extract ONLY outgoing expenses (money the
> user SPENT) and return JSON
> `{"expenses": [{"amount", "currency", "occurred_at", "merchant"}]}`.
> **Skip incoming money completely** — incoming transfers and top-ups
> (поповнення, зарахування, переказ від, надходження), cashback, salary and
> pensions. `amount` must be positive; `currency` is **always "UAH"**
> (never USD/EUR/PLN).

---

## 🚀 Setup guide

### 1. Prerequisites

- Python **3.12+**
- **Tesseract OCR** (for the default OCR engine):
  ```bash
  # Ubuntu/Debian
  sudo apt-get install -y tesseract-ocr tesseract-ocr-ukr
  # macOS
  brew install tesseract tesseract-lang
  ```
- A **Telegram bot token** from [@BotFather](https://t.me/BotFather)
- A **Google Gemini API key** (optional but recommended) from
  [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

### 2. Configure

```bash
cp .env.example .env
# edit .env and set BOT_TOKEN and GEMINI_API_KEY
```

### 3. Install & migrate

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

### 4. Run

```bash
python -m app.main
```

Then open Telegram, message your bot, and send a screenshot. 🎉

### 5. Run with Docker

```bash
docker compose up --build
```

(The SQLite database is persisted to `./data`.)

---

## 🧪 Development

```bash
pip install -r requirements-dev.txt

ruff check .                 # lint
pytest -q                    # unit tests
python -m scripts.smoke_test # end-to-end pipeline (synthetic screenshot, no Telegram)
```

### Creating a new migration

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

---

## 🔧 Configuration reference

| Variable | Default | Description |
|----------|---------|-------------|
| `BOT_TOKEN` | – | Telegram bot token (required) |
| `GEMINI_API_KEY` | – | Google Gemini key (optional; enables AI parsing) |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Gemini chat model used |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/expenses.db` | Async SQLAlchemy URL |
| `OCR_ENGINE` | `tesseract` | `tesseract` or `easyocr` |
| `OCR_LANGUAGES` | `eng+ukr` | OCR languages |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ALLOWED_USER_IDS` | – | Comma-separated allow-list (empty = everyone) |

### Using EasyOCR instead of Tesseract

EasyOCR is heavier (it pulls in PyTorch) but can be more robust on noisy
screenshots. Enable it with:

```bash
pip install easyocr
# in .env
OCR_ENGINE=easyocr
OCR_LANGUAGES=en,uk
```
