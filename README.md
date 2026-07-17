# AUTOVIEW

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
├── docs/
│   └── SETUP_GOOGLE.md
├── scripts/
│   └── acceso_remoto.sh    # Tailscale/ngrok/Cloudflare
├── src/
│   ├── __init__.py
│   ├── state.py            # SQLite state management
│   ├── config.py           # Settings with .env support
│   ├── gmail_reader.py     # Gmail API wrapper
│   ├── event_extractor.py  # LLM event extraction
│   ├── calendar_writer.py  # Google Calendar API
│   └── telegram_reporter.py # Telegram bot
└── config/                 # OAuth credentials (gitignored)
    ├── credentials.json
    └── token.json
```

## Tech Stack

- **Python** 3.11+
- **FastAPI** — Dashboard backend
- **Streamlit** — Dashboard frontend
- **Google APIs** — Gmail + Calendar
- **OpenRouter / Ollama** — LLM providers
- **SQLite** — Local state
- **systemd** — Production scheduler

## License

MIT
