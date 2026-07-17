"""
config.py — Carga configuración desde variables de entorno.

Toda la configuración sensible vive en config/.env (no se commitea).
Proyecto: AUTOVIEW
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Raíz del proyecto (sube 1 nivel desde src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Cargar .env automáticamente
_env_path = PROJECT_ROOT / "config" / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


@dataclass
class Config:
    """Configuración global del proyecto."""

    # --- Google ---
    credentials_file: Path = PROJECT_ROOT / "config" / "credentials.json"
    token_file: Path = PROJECT_ROOT / "data" / "token.json"
    gmail_query: str = os.getenv("GMAIL_QUERY", "from:@universidad.edu OR subject:(examen|evento|calendario|entrega|parcial|final)")
    max_emails_per_run: int = int(os.getenv("MAX_EMAILS_PER_RUN", "20"))

    # --- LLM ---
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")  # "ollama" | "openai" | "openrouter" | "gemini"
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # --- Calendar ---
    calendar_id: str = os.getenv("CALENDAR_ID", "primary")
    timezone: str = os.getenv("TIMEZONE", "America/Mexico_City")

    # --- Estado ---
    db_path: Path = PROJECT_ROOT / "data" / "state.db"

    # --- Logging ---
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    def validate(self) -> list[str]:
        """Retorna lista de errores de configuración. Vacía = todo OK."""
        errors = []
        if not self.credentials_file.exists():
            errors.append(f"No existe {self.credentials_file}. Ver docs/SETUP_GOOGLE.md")
        if self.llm_provider in ("openai", "openrouter") and not self.openai_api_key:
            errors.append(f"LLM_PROVIDER={self.llm_provider} pero OPENAI_API_KEY está vacío")
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            errors.append("LLM_PROVIDER=gemini pero GEMINI_API_KEY está vacío. Saca tu API key de: https://aistudio.google.com/apikey")
        return errors


# Singleton
config = Config()
