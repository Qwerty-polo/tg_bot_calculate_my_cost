# Telegram Expense Tracker

A Python Telegram bot that turns banking screenshots into a personal expense
ledger with weekly and monthly budgets. Built as a backend portfolio MVP using
async handlers, OCR, optional Gemini extraction, SQLAlchemy, and Alembic.

SQLite and long polling are intentional choices for a small, single-instance
application. This project is not production-ready financial software.

## Features

- Extract expenses from screenshots sent as Telegram **photos**.
- Use Gemini when configured, or a conservative local fallback parser.
- Validate amounts and filter likely incoming-money transactions.
- Set weekly/monthly spending limits and view totals and remaining budgets.
- Detect exact repeat image uploads per user.
- Reset your expenses, budgets, and upload fingerprints after confirmation.
- Keep financial interactions in private chats.

| Command | Action |
| --- | --- |
| `/start`, `/help` | Introduction and usage instructions |
| `/set_week_budget 5000` | Set a weekly limit, or omit the amount for a prompt |
| `/set_month_budget 20000` | Set a monthly limit, or omit the amount for a prompt |
| `/cancel` | Cancel pending budget input |
| `/today` | List today's recorded expenses |
| `/stats` | Show daily, weekly, and monthly totals against budgets |

The **Reset Statistics** button is available in the private-chat menu.

## Tech stack

- **Python 3.12** — the version used by CI and Docker.
- **aiogram 3** — async Telegram handlers, routers, middleware, and FSM.
- **SQLAlchemy 2 + aiosqlite** — async SQLite persistence; **Alembic** migrations.
- **Pydantic 2 + pydantic-settings** — validation and environment configuration.
- **Tesseract + pytesseract + Pillow** — local OCR; optional EasyOCR support.
- **Google Gemini** — called through the OpenAI Python SDK using Google's endpoint.
- **pytest / pytest-asyncio, Ruff, GitHub Actions, Docker Compose** — validation and tooling.

Exact dependency versions are in [requirements.txt](requirements.txt) and
[requirements-dev.txt](requirements-dev.txt).

## Architecture and screenshot processing

```text
Telegram photo → local OCR → Gemini or fallback parser → validation → SQLite
                                                                      ↓
                                                        commit → Telegram summary
```

OCR runs in a worker thread. Gemini receives the extracted text, not the image.
If its key is empty or an AI request/parsing step fails, the fallback accepts only
clear same-line entries such as `Silpo 230.50 грн`. Ambiguous lines are skipped.
Amounts must be finite, positive, have at most two decimal places, and fit the
database's `Numeric(12, 2)` range. Income filtering is heuristic and can make mistakes.

Handlers use short database transactions, finishing commits before success replies.
A failed Telegram confirmation does not roll back saved records. Each successful
upload stores a per-user SHA-256 image fingerprint atomically with its expenses.

```text
app/
├── main.py       # Entry point and long polling
├── bot/          # Bot/dispatcher factories and command menu
├── handlers/     # Commands, budget conversations, uploads, statistics, reset
├── middlewares/  # Private-chat guard, authorization, session/service injection, logs
├── services/     # User, expense, budget, and duplicate-upload persistence
├── models/       # users, expenses, budgets, uploads
├── database/     # Async engine, sessions, declarative base
├── config/       # Environment settings
├── ai/           # Gemini client, prompts, schemas, fallback parser
├── ocr/          # Image preprocessing and OCR engines
└── utils/        # Money validation, formatting, date boundaries, logging
alembic/          # Versioned schema migrations
tests/            # Unit, database, dispatcher, and migration regression tests
scripts/          # Optional manual pipeline smoke test
docs/images/      # Reserved for real, redacted demo screenshots
```

## Local setup

Run commands from the repository root. Use Python 3.12, a Telegram token from
[@BotFather](https://t.me/BotFather), and Tesseract with English/Ukrainian language
data. Gemini is optional; obtain a key from
[Google AI Studio](https://aistudio.google.com/apikey) if needed.

Install Tesseract on Ubuntu/Debian:

```bash
sudo apt-get install -y tesseract-ocr tesseract-ocr-ukr
```

On macOS, use `brew install tesseract tesseract-lang`. On Windows, install
Tesseract and set `TESSERACT_CMD` to its executable path if it is not on `PATH`.

Create and activate an environment, then copy the configuration:

```bash
# Linux/macOS
python3.12 -m venv .venv
source .venv/bin/activate
cp .env.example .env
```

```powershell
# Windows PowerShell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
```

Edit `.env`: set `BOT_TOKEN` and either supply a real `GEMINI_API_KEY` or set it
to an empty value. The example key is a placeholder, not a working credential.
For a personal deployment, set `ALLOWED_USER_IDS` to your Telegram user ID.

```bash
python -m pip install -r requirements.txt
alembic upgrade head
python -m app.main
```

Open a private chat with your bot, send `/start`, and upload a banking screenshot
as a photo. Stop the local process with Ctrl+C.

## Environment variables

See [.env.example](.env.example). Only `BOT_TOKEN` is required; the other settings
have defaults or are optional.

| Variable | Default / purpose |
| --- | --- |
| `BOT_TOKEN` | Required Telegram bot token |
| `GEMINI_API_KEY` | Empty disables Gemini and uses fallback parsing |
| `GEMINI_MODEL` | `gemini-3.5-flash` |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/expenses.db` |
| `OCR_ENGINE` | `tesseract`; alternatively `easyocr` |
| `OCR_LANGUAGES` | `eng+ukr` for Tesseract |
| `TESSERACT_CMD` | Empty uses `PATH`; otherwise the Tesseract executable path |
| `LOG_LEVEL` | `INFO` |
| `ALLOWED_USER_IDS` | Comma-separated Telegram user IDs; empty allows everyone |

EasyOCR requires a separate `python -m pip install easyocr`, then
`OCR_ENGINE=easyocr` and `OCR_LANGUAGES=en,uk`. It brings heavier dependencies,
including PyTorch; the default setup uses Tesseract.

## Database migrations

Run `alembic upgrade head` **before the first bot startup** and after pulling
schema changes. It creates the SQLite directory and applies migrations, including
the upload-fingerprint table. Back up existing data before an upgrade.

For development schema changes:

```bash
alembic revision --autogenerate -m "describe change"
# Review the generated migration before applying it.
alembic upgrade head
```

Startup also calls `create_all()`, which creates missing tables but does not
upgrade existing ones or establish an Alembic revision. An older database created
only this way needs a verified migration baseline; do not blindly stamp it or
assume `create_all()` replaces migrations.

## Docker

Create and configure `.env` as above. Docker installs Tesseract, so no host OCR
installation is needed. With Docker and Compose installed:

```bash
docker compose build
docker compose run --rm bot alembic upgrade head
docker compose up -d
docker compose logs -f bot
```

SQLite persists in the host's `./data` directory. Compose supplies `.env` at
runtime; `.dockerignore` keeps local secrets and artifacts out of the image.
Migrations are **not automatic**. For upgrades, stop the bot with
`docker compose down`, back up `./data`, then repeat the build/migrate/start steps.
The same migration-baseline caveat applies to older databases.

## Tests and code quality

```bash
python -m pip install -r requirements-dev.txt
ruff check .
python -m pytest -q
```

The suite covers parsing, validation, user isolation, FSM routing, private-chat
guards, commit/reply failures, duplicate uploads, logging privacy, build-context
rules, and migrations. Telegram, OCR, and AI are mocked in dispatcher tests;
tests do not require live credentials. CI runs lint, tests, and a migration check.

The optional `python -m scripts.smoke_test` exercises OCR through persistence with
a synthetic input. It requires OCR, writes to a database, and may call Gemini.
Use a disposable `DATABASE_URL`: the default is `./data/smoke.db`, but an existing
environment value takes precedence. This is a manual demonstration, not an
assertion-based test or a portfolio screenshot.

## Privacy and security

- Financial operations are restricted to private chats. `/start`, `/help`, and
  `/cancel` remain available in groups.
- Message logs omit full message bodies and profile details. Never publish real
  banking screenshots, `.env`, database files, or logs containing personal data.
- OCR text is stored unencrypted in SQLite and sent to Google when Gemini is
  enabled. Protect the database and use redacted inputs for demonstrations.
- Reset removes expenses, budgets, and fingerprints; the user profile remains.
- This MVP has no application-level rate limiting. Use the allow-list for a
  personal deployment.

## Known limitations

- **Exact duplicates only:** cropped/recompressed images and overlapping
  transaction lists are not deduplicated. Uploads predating fingerprint support
  cannot be detected retrospectively.
- **No bank synchronization:** users upload screenshots manually; images sent as
  Telegram documents are not handled.
- **No individual transaction editing/deletion:** only a full statistics reset
  is available. OCR/AI extraction and income filtering can be inaccurate.
- **Historical dates:** a parsed purchase date is retained only if it matches
  the current UTC day; other dates are replaced with processing time. Statistics
  use UTC boundaries, not the user's local timezone.
- **No currency conversion:** amounts are stored/displayed as UAH. AI output in
  another currency is relabeled without conversion; fallback accepts explicit
  UAH amounts only. Use UAH screenshots.
- **MVP operation:** SQLite and long polling target a single instance. Pending
  conversations are in memory and disappear on restart. Large expense lists
  are not paginated and may exceed Telegram's message-length limit.

## Demo screenshots

Real, redacted screenshots can be added to `docs/images/`. No screenshots are
included yet.

<!-- Portfolio image slots: add Markdown image links only after the files exist.
docs/images/start-help.png — private-chat introduction and available commands
docs/images/expense-extraction.png — successful extraction using redacted demo data
docs/images/statistics-budget.png — totals and remaining weekly/monthly budgets
Remove names, account/card numbers, balances, and other personal details before upload.
-->

## Author and contact

Maintained by [Qwerty-polo](https://github.com/Qwerty-polo).
For questions or feedback, use the
[repository issues](https://github.com/Qwerty-polo/tg_bot_calculate_my_cost/issues).
