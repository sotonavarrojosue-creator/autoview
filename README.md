# AUTOVIEW

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Systemd](https://img.shields.io/badge/Systemd-Timer-orange?logo=linux)](https://systemd.io)

Gmail → LLM → Google Calendar automation with systemd timer and Telegram reporter.

## What it does

1. **Reads** unread Gmail emails (every 3h via systemd timer)
2. **Extracts** events, tasks, deadlines using LLM (OpenRouter or local Ollama)
3. **Creates** events in Google Calendar
4. **Reports** summary via Telegram

## Architecture

```
┌─────────┐     ┌─────────┐     ┌──────────────┐     ┌─────────────┐
│ Gmail   │────▶│ LLM     │────▶│ Google       │────▶│ Telegram    │
│ API     │     │ (Event  │     │ Calendar     │     │ Reporter    │
│         │     │ Extract)│     │ API          │     │             │
└─────────┘     └─────────┘     └──────────────┘     └─────────────┘
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure credentials
cp .env.example .env
# Edit .env with your API keys

# 3. Set up Google OAuth (one-time)
# Follow docs/SETUP_GOOGLE.md

# 4. Run manually
python main.py

# 5. Install as systemd service (runs every 3h)
sudo ./install.sh
```

## Project Structure

```
autoview/
├── main.py                 # Entry point
├── app.py                  # Streamlit dashboard
├── dashboard.py            # Dashboard components
├── requirements.txt
├── install.sh              # Systemd installer
├── run-dashboard.sh        # Dashboard launcher
├── config/                 # OAuth credentials (gitignored)
├── data/                   # SQLite state (gitignored)
├── docs/
│   └── SETUP_GOOGLE.md
├── src/
│   ├── __init__.py
│   ├── state.py            # SQLite state management
│   ├── config.py           # Settings with .env support
│   ├── gmail_reader.py     # Gmail API wrapper
│   ├── event_extractor.py  # LLM event extraction
│   ├── calendar_writer.py  # Calendar API wrapper
│   └── telegram_reporter.py # Telegram bot
└── tests/
```

## Tech Stack

- **Python** 3.11+
- **Gmail API** / **Google Calendar API** (OAuth2)
- **OpenRouter** (multi-model) or **Ollama** (local)
- **Streamlit** (dashboard)
- **systemd** (scheduling)
- **SQLite** (state persistence)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GMAIL_CREDENTIALS_PATH` | Yes | Path to Google OAuth credentials.json |
| `GMAIL_TOKEN_PATH` | Yes | Path to token.json (auto-generated) |
| `CALENDAR_CREDENTIALS_PATH` | Yes | Path to Google OAuth credentials.json |
| `CALENDAR_TOKEN_PATH` | Yes | Path to token.json (auto-generated) |
| `OPENROUTER_API_KEY` | **Yes** (for AI) | Get from [openrouter.ai/keys](https://openrouter.ai/keys) |
| `OPENROUTER_MODEL` | No | Default: `openai/gpt-4o-mini` |
| `OLLAMA_HOST` | No | Default: `http://localhost:11434` |
| `OLLAMA_MODEL` | No | Default: `llama3.1:8b` |
| `TELEGRAM_BOT_TOKEN` | No | For Telegram reports |
| `TELEGRAM_CHAT_ID` | No | Your chat ID |
| `SCHEDULE_INTERVAL_HOURS` | No | Default: 3 |

## License

MIT
