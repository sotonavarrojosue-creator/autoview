"""
telegram_reporter.py — Envía reportes de AUTOVIEW a Telegram.

Usa el mismo bot token que OpenClaw (lee de ~/.openclaw/openclaw.json).
No depende de OpenClaw Gateway — habla directo con la API de Telegram.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger

from .state import get_stats, get_recent, get_timeline_stats

# Ruta a la config de OpenClaw (contiene el bot token de Telegram)
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"


def _get_bot_token() -> Optional[str]:
    """Lee el bot token de Telegram desde la config de OpenClaw."""
    if not OPENCLAW_CONFIG.exists():
        logger.error(f"No existe {OPENCLAW_CONFIG}")
        return None

    try:
        data = json.loads(OPENCLAW_CONFIG.read_text())
        token = data.get("channels", {}).get("telegram", {}).get("botToken")
        if not token or token == "[REDACTED-TELEGRAM-TOKEN]":
            logger.error("Bot token no encontrado o redactado en openclaw.json")
            return None
        return token
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error leyendo openclaw.json: {e}")
        return None


def _send_telegram(token: str, message: str, chat_id: str = "") -> bool:
    """
    Envía un mensaje a Telegram vía Bot API.

    Si no se especifica chat_id, intenta obtenerlo del owner configurado
    en OpenClaw (commands.ownerAllowFrom).
    """
    if not chat_id:
        chat_id = _get_owner_chat_id()

    if not chat_id:
        logger.error("No hay chat_id destino para el mensaje Telegram")
        return False

    # Escapar caracteres especiales para MarkdownV2
    text = _escape_markdown(message)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("ok"):
                logger.info("✅ Reporte enviado a Telegram")
                return True
            else:
                logger.error(f"Telegram API error: {result}")
                return False
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        logger.error(f"Error enviando a Telegram: {e}")
        return False


def _get_owner_chat_id() -> Optional[str]:
    """Obtiene el chat_id del owner desde OpenClaw config."""
    try:
        data = json.loads(OPENCLAW_CONFIG.read_text())
        allow_from = data.get("commands", {}).get("ownerAllowFrom", [])
        for entry in allow_from:
            if entry.startswith("telegram:"):
                return entry.split(":")[1]
    except (json.JSONDecodeError, KeyError, OSError):
        pass
    return None


def _escape_markdown(text: str) -> str:
    """Escapa caracteres reservados para MarkdownV2 de Telegram."""
    chars = r"_*[]()~`>#+-=|{}.!"
    for c in chars:
        text = text.replace(c, f"\\{c}")
    return text


def build_report(days: int = 4) -> str:
    """
    Construye el texto del reporte en formato legible.

    Args:
        days: Cuántos días hacia atrás incluir.

    Returns:
        Texto plano del reporte (sin escapar, para construcción).
    """
    stats = get_stats()
    recent = get_recent(limit=50)
    timeline = get_timeline_stats(days=days)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    # Filtrar solo los recientes (últimos N días)
    recent_items = [
        r for r in recent
        if datetime.fromisoformat(r["processed_at"]) >= cutoff
    ]

    events_in_period = sum(1 for r in recent_items if r["has_event"])
    errors_in_period = sum(1 for r in recent_items if r["status"] == "error")

    lines = []
    lines.append("📬 *AUTOVIEW — Reporte Automático*")
    lines.append(f"📅 Últimos {days} días")
    lines.append("")

    # Resumen del período
    lines.append("┌─ 📊 *Resumen del período*")
    lines.append(f"│ Correos procesados:  {len(recent_items)}")
    lines.append(f"│ Eventos creados:      {events_in_period}")
    lines.append(f"│ Errores:              {errors_in_period}")
    lines.append("")

    # Totales históricos
    lines.append("┌─ 📈 *Totales históricos*")
    lines.append(f"│ Correos procesados:  {stats['total_processed']}")
    lines.append(f"│ Eventos creados:      {stats['events_created']}")
    lines.append(f"│ Errores:              {stats['errors']}")
    lines.append("")

    # Eventos creados en el período
    event_items = [r for r in recent_items if r["has_event"]]
    if event_items:
        lines.append(f"┌─ 🎯 *Eventos creados ({len(event_items)})*")
        for item in event_items[:10]:  # top 10
            title = item["event_title"] or "(sin título)"
            start = item["event_start"] or ""
            if start:
                try:
                    dt = datetime.fromisoformat(start)
                    start_fmt = dt.strftime("%d/%m %H:%M")
                except ValueError:
                    start_fmt = start[:10]
            else:
                start_fmt = "?"
            lines.append(f"│ • {title} — {start_fmt}")
        if len(event_items) > 10:
            lines.append(f"│   ... y {len(event_items) - 10} más")
        lines.append("")

    # Errores
    error_items = [r for r in recent_items if r["status"] == "error"]
    if error_items:
        lines.append("┌─ ❌ *Errores*")
        for item in error_items[:5]:
            lines.append(f"│ • {item['subject'][:60]}")
        lines.append("")

    # Próxima ejecución
    lines.append("┌─ ⏰ *Próximo reporte*")
    lines.append("│ En 4 días — mantenimiento automático")
    lines.append("")
    lines.append("─" * 20)
    lines.append("AUTOVIEW · Gmail → Calendar + Telegram")
    lines.append(f"ID: {now.strftime('%Y%m%d-%H%M%S')}")

    return "\n".join(lines)


def send_report(days: int = 4, chat_id: str = "") -> bool:
    """
    Envía el reporte de AUTOVIEW a Telegram.

    Args:
        days: Período del reporte en días.
        chat_id: Chat ID de Telegram (opcional, auto-detecta).

    Returns:
        True si se envió correctamente.
    """
    token = _get_bot_token()
    if not token:
        return False

    report = build_report(days=days)
    return _send_telegram(token, report, chat_id=chat_id)


# === Punto de entrada directo ===
if __name__ == "__main__":
    from .config import config
    from .state import init_db
    init_db()
    send_report()
