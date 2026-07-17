"""
state.py — Persistencia de estado con SQLite (AUTOVIEW).

Registra qué correos ya fueron procesados y qué evento se creó.
Evita duplicados: si el script se corre 2 veces, no crea 2 eventos iguales.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger

from .config import config


def _get_conn() -> sqlite3.Connection:
    """Conexión a la DB (la crea si no existe)."""
    conn = sqlite3.connect(str(config.db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Crea las tablas si no existen. Idempotente."""
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_emails (
                email_id      TEXT PRIMARY KEY,
                thread_id     TEXT,
                subject       TEXT,
                sender        TEXT,
                processed_at  TEXT NOT NULL,
                has_event     INTEGER NOT NULL DEFAULT 0,
                event_id      TEXT,           -- ID del evento en Google Calendar
                event_title   TEXT,
                event_start   TEXT,
                status        TEXT NOT NULL DEFAULT 'processed'
                -- 'processed' | 'error' | 'skipped'
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_processed_status
            ON processed_emails(status)
            """
        )
    logger.debug(f"DB inicializada en {config.db_path}")


def is_processed(email_id: str) -> bool:
    """True si el email ya fue procesado antes."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_emails WHERE email_id = ?",
            (email_id,),
        ).fetchone()
    return row is not None


def mark_processed(
    email_id: str,
    thread_id: str,
    subject: str,
    sender: str,
    has_event: bool,
    event_id: Optional[str] = None,
    event_title: Optional[str] = None,
    event_start: Optional[str] = None,
    status: str = "processed",
) -> None:
    """Registra un email como procesado."""
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO processed_emails
                (email_id, thread_id, subject, sender, processed_at,
                 has_event, event_id, event_title, event_start, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email_id, thread_id, subject, sender, now,
                int(has_event), event_id, event_title, event_start, status,
            ),
        )
    logger.debug(
        f"Email {email_id} marcado como procesado "
        f"(has_event={has_event}, status={status})"
    )


def get_stats() -> dict:
    """Estadísticas para mostrar en el resumen."""
    with _get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM processed_emails"
        ).fetchone()[0]
        with_event = conn.execute(
            "SELECT COUNT(*) FROM processed_emails WHERE has_event = 1"
        ).fetchone()[0]
        errors = conn.execute(
            "SELECT COUNT(*) FROM processed_emails WHERE status = 'error'"
        ).fetchone()[0]
    return {
        "total_processed": total,
        "events_created": with_event,
        "errors": errors,
    }


def get_recent(limit: int = 20) -> list[dict]:
    """Últimos N registros procesados (para debug)."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT email_id, subject, sender, processed_at,
                   has_event, event_title, event_start, status
            FROM processed_emails
            ORDER BY processed_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_emails(
    limit: int = 100, offset: int = 0,
    status_filter: Optional[str] = None,
    sender_filter: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[list[dict], int]:
    """Retorna lista paginada de emails + total (para dashboard)."""
    conditions = []
    params: list = []

    if status_filter:
        conditions.append("status = ?")
        params.append(status_filter)
    if sender_filter:
        conditions.append("sender LIKE ?")
        params.append(f"%{sender_filter}%")
    if search:
        conditions.append("(subject LIKE ? OR event_title LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    with _get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM processed_emails {where}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT email_id, thread_id, subject, sender, processed_at,
                   has_event, event_id, event_title, event_start, status
            FROM processed_emails
            {where}
            ORDER BY processed_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()
    return [dict(r) for r in rows], total


def get_email_by_id(email_id: str) -> Optional[dict]:
    """Retorna un registro específico por email_id."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM processed_emails WHERE email_id = ?",
            (email_id,),
        ).fetchone()
    return dict(row) if row else None


def update_email_record(email_id: str, **kwargs) -> bool:
    """
    Actualiza campos de un registro.
    kwargs puede incluir: subject, sender, has_event, event_id,
    event_title, event_start, status
    """
    if not kwargs:
        return False
    allowed = {"subject", "sender", "has_event", "event_id",
               "event_title", "event_start", "status"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [email_id]

    with _get_conn() as conn:
        try:
            conn.execute(
                f"UPDATE processed_emails SET {set_clause} WHERE email_id = ?",
                values,
            )
            return conn.total_changes > 0
        except sqlite3.Error as e:
            logger.error(f"Error actualizando {email_id}: {e}")
            return False


def delete_email_record(email_id: str) -> bool:
    """Elimina un registro de la DB."""
    with _get_conn() as conn:
        try:
            conn.execute(
                "DELETE FROM processed_emails WHERE email_id = ?",
                (email_id,),
            )
            return conn.total_changes > 0
        except sqlite3.Error as e:
            logger.error(f"Error eliminando {email_id}: {e}")
            return False


def get_timeline_stats(days: int = 30) -> list[dict]:
    """Agrupación por día para gráfica de timeline."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT DATE(processed_at) as day,
                   COUNT(*) as total,
                   SUM(CASE WHEN has_event = 1 THEN 1 ELSE 0 END) as events,
                   SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
            FROM processed_emails
            WHERE processed_at >= datetime('now', ?)
            GROUP BY DATE(processed_at)
            ORDER BY day DESC
            """,
            (f"-{days} days",),
        ).fetchall()
    return [dict(r) for r in rows]


def get_sender_stats() -> list[dict]:
    """Estadísticas agrupadas por remitente."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT sender,
                   COUNT(*) as total,
                   SUM(CASE WHEN has_event = 1 THEN 1 ELSE 0 END) as events,
                   SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
            FROM processed_emails
            GROUP BY sender
            ORDER BY total DESC
            LIMIT 20
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_events_by_date_range(start_date: str, end_date: str) -> list[dict]:
    """Eventos en un rango de fechas."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT email_id, subject, sender, event_title, event_start, status
            FROM processed_emails
            WHERE has_event = 1
              AND event_start >= ?
              AND event_start <= ?
            ORDER BY event_start ASC
            """,
            (start_date, end_date),
        ).fetchall()
    return [dict(r) for r in rows]
