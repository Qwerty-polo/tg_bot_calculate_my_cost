# 🤖 AI Expense Tracker — Telegram Bot

An AI-powered Telegram bot for **personal expense tracking from banking
screenshots**. Send a screenshot from Monobank, Privat24, A‑Bank (or any
banking app) and the bot will:

1. **OCR** the image to extract the raw transaction text.
2. **Understand** the transactions with an LLM and turn them into structured
   records (amount, currency, datetime, merchant, category, description).
3. **Categorize** each purchase automatically (food, transport, shopping, …).
4. **Track budgets** (weekly / monthly) and generate **smart financial
   insights** and **charts**.

Built with **aiogram 3**, **SQLAlchemy 2 (async)**, **Alembic**, **OpenAI**,
**pytesseract/easyocr** and **matplotlib**. Fully asynchronous, Python 3.12+,
Docker-ready.

---

## ✨ Features

- 📷 **Screenshot analysis** — OCR + AI extraction of every transaction.
- 🏷️ **Automatic categorization** into: food, transport, shopping,
  entertainment, subscriptions, cafes, health, utilities, other.
- 🎯 **Budget planning** — `/set_week_budget`, `/set_month_budget`.
- 🧠 **AI financial analysis** — % of budget spent, remaining balance, biggest
  category, biggest purchase, daily average, and pace warnings.
- 📊 **Statistics commands** — `/today`, `/week`, `/month`, `/stats`,
  `/categories`, `/budget_status`.
- 📈 **Charts** — category pie chart, weekly spending bar chart, monthly trend.
- 🔁 **Smart detection** — recurring subscriptions, unusually high spending,
  week-over-week comparison, AI saving recommendations.
- 🎨 **Beautiful formatting** — emojis, progress bars, percentages.

---

## 🗂️ Project structure

```
app/
├── main.py            # entrypoint (long-polling)
├── bot/               # Bot + Dispatcher factories, command menu
├── config/            # pydantic-settings configuration (.env)
├── handlers/          # aiogram routers: common, screenshots, budgets, stats
├── services/          # DB business logic: user / expense / budget services
├── database/          # async engine, session, declarative base
├── models/            # SQLAlchemy models + enums
├── ai/                # OpenAI client, prompts, parsing & analysis
├── ocr/               # OCR service (tesseract / easyocr)
├── analytics/         # metrics, subscription & anomaly detection
├── charts/            # matplotlib chart generation
├── middlewares/       # logging + session/services injection
└── utils/             # formatting, timeframes, logging config
alembic/               # database migrations
tests/                 # unit tests (pure analytics, parsing, formatting)
scripts/smoke_test.py  # end-to-end pipeline smoke test (no Telegram needed)
```

---

## 🗄️ Database schema

SQLite (MVP) via async SQLAlchemy; migrations managed by Alembic.

| Table       | Key columns |
|-------------|-------------|
| **users**   | `id`, `telegram_id` (unique), `username`, `full_name`, `currency`, `created_at` |
| **expenses**| `id`, `user_id → users.id`, `amount`, `currency`, `occurred_at`, `merchant`, `category`, `description`, `raw_text`, `created_at` |
| **budgets** | `id`, `user_id → users.id`, `period` (week/month), `amount`, `currency`, `created_at` — unique per (user, period) |
| **analytics** | `id`, `user_id → users.id`, `period`, `metrics_json`, `insight_text`, `created_at` |

---

## ⚙️ How OCR + AI processing works

```
Screenshot (photo)
   │  message.bot.download()
   ▼
OCR (app/ocr)            tesseract or easyocr, with light preprocessing
   │  raw text
   ▼
AI parsing (app/ai)      OpenAI chat completion, response_format=json_object
   │  validated with Pydantic (app/ai/schemas.ParsedExpense)
   ▼
Persistence (services)   ExpenseService.add_many()
   │
   ▼
Analytics (app/analytics)  metrics dict (budget %, categories, anomalies, …)
   │
   ├── deterministic formatting (utils/formatting) → message text
   ├── AI narrative (app/ai)                        → human insights
   └── charts (app/charts)                          → PNG images
```

**Graceful degradation:** if `OPENAI_API_KEY` is not set, the bot still works:
- transaction parsing falls back to a regex heuristic parser, and
- insights/recommendations fall back to deterministic templates.

OCR runs in a worker thread (`asyncio.to_thread`) so the event loop is never
blocked; charts are generated the same way.

### Example AI prompts

The exact prompts live in [`app/ai/prompts.py`](app/ai/prompts.py). In short:

**Transaction extraction (system):**

> You are a meticulous financial data extraction engine… You receive raw OCR
> text from Ukrainian banking apps… Extract ONLY outgoing expenses and return
> JSON `{"expenses": [{"amount", "currency", "occurred_at", "merchant",
> "category", "description"}]}`. Ignore incoming transfers and balances.
> `amount` must be positive; `category` must be one of food, transport,
> shopping, entertainment, subscriptions, cafes, health, utilities, other.

**Financial analysis (system):**

> You are a friendly personal finance assistant. Given precomputed metrics,
> write a short, concrete analysis (3–5 lines): % of budget spent, remaining
> balance, biggest category, biggest purchase, daily average, and a pace
> warning. Never invent numbers.

Example generated insights:

- "You already spent 72% of your weekly budget."
- "Most of your money this week went to food (43%)."
- "Your biggest expense was Rozetka — 1850 UAH."
- "If you continue spending at this pace, you may exceed your budget in 3 days."

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
- An **OpenAI API key** (optional but recommended) from
  [platform.openai.com](https://platform.openai.com/api-keys)

### 2. Configure

```bash
cp .env.example .env
# edit .env and set BOT_TOKEN and OPENAI_API_KEY
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
| `OPENAI_API_KEY` | – | OpenAI key (optional; enables AI parsing & insights) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model used |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/expenses.db` | Async SQLAlchemy URL |
| `OCR_ENGINE` | `tesseract` | `tesseract` or `easyocr` |
| `OCR_LANGUAGES` | `eng+ukr` | OCR languages |
| `DEFAULT_CURRENCY` | `UAH` | Default currency |
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
