"""
gmail_reader.py — Lee correos de Gmail aplicando filtros (AUTOVIEW).

Usa la Gmail API para buscar correos relevantes y extraer su contenido
en texto plano (limpiando HTML).
"""
from __future__ import annotations

import base64
import email.utils
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from loguru import logger

from .config import config


@dataclass
class EmailMessage:
    """Representa un correo procesado listo para analizar."""
    id: str
    thread_id: str
    sender: str
    subject: str
    date: str  # ISO format
    body_text: str  # texto plano, sin HTML
    snippet: str  # preview corto


def get_gmail_service(creds: Credentials):
    """Crea el cliente de la Gmail API."""
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def fetch_emails(creds: Credentials) -> list[EmailMessage]:
    """
    Busca correos según config.gmail_query y los retorna procesados.

    Returns:
        Lista de EmailMessage (vacía si error o sin resultados).
    """
    try:
        service = get_gmail_service(creds)
    except HttpError as e:
        logger.error(f"Error conectando a Gmail: {e}")
        return []

    try:
        # 1. Buscar IDs de mensajes
        results = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=config.gmail_query,
                maxResults=config.max_emails_per_run,
            )
            .execute()
        )
        messages = results.get("messages", [])
        if not messages:
            logger.info("No hay correos nuevos que coincidan con el filtro")
            return []

        logger.info(f"Encontrados {len(messages)} correos candidatos")

        # 2. Obtener detalle de cada mensaje (batch sería mejor, pero esto es más simple)
        emails: list[EmailMessage] = []
        for msg_ref in messages:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_ref["id"], format="full")
                .execute()
            )
            parsed = _parse_message(msg)
            if parsed:
                emails.append(parsed)

        logger.info(f"Procesados {len(emails)} correos correctamente")
        return emails

    except HttpError as e:
        logger.error(f"Error leyendo Gmail: {e}")
        return []


def _parse_message(msg: dict) -> Optional[EmailMessage]:
    """Extrae campos relevantes de un mensaje de la API de Gmail."""
    try:
        # Headers
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        sender = headers.get("From", "desconocido")
        subject = headers.get("Subject", "(sin asunto)")
        date_raw = headers.get("Date", "")
        date_iso = _parse_date(date_raw)

        # Cuerpo
        body_text = _extract_body(msg["payload"])
        snippet = msg.get("snippet", "")[:200]

        return EmailMessage(
            id=msg["id"],
            thread_id=msg.get("threadId", ""),
            sender=sender,
            subject=subject,
            date=date_iso,
            body_text=body_text,
            snippet=snippet,
        )
    except Exception as e:
        logger.warning(f"Error parseando mensaje {msg.get('id', '?')}: {e}")
        return None


def _extract_body(payload: dict) -> str:
    """
    Extrae el texto del cuerpo del correo.
    Maneja multipart y HTML → texto plano.
    """
    body = ""

    if "parts" in payload:
        # Multipart: buscar text/plain primero, si no, text/html
        for part in payload["parts"]:
            mime = part.get("mimeType", "")
            if mime == "text/plain":
                body = _decode_part(part)
                break
            elif mime == "text/html" and not body:
                body = _decode_part(part)
        # Si no encontró en parts directos, buscar recursivo
        if not body:
            for part in payload["parts"]:
                if "parts" in part:
                    body = _extract_body(part)
                    if body:
                        break
    else:
        # Mensaje simple
        body = _decode_part(payload)

    # Si es HTML, limpiarlo
    if body and "<" in body and ">" in body:
        soup = BeautifulSoup(body, "lxml")
        body = soup.get_text(separator="\n", strip=True)

    # Limitar tamaño para no saturar el LLM
    return body[:5000] if body else ""


def _decode_part(part: dict) -> str:
    """Decodifica el body de una parte (base64)."""
    body_data = part.get("body", {}).get("data", "")
    if not body_data:
        return ""
    # Gmail usa URL-safe base64
    decoded = base64.urlsafe_b64decode(body_data + "===").decode(
        "utf-8", errors="ignore"
    )
    return decoded


def _parse_date(date_raw: str) -> str:
    """Convierte fecha RFC 2822 a ISO 8601."""
    if not date_raw:
        return ""
    try:
        dt = email.utils.parsedate_to_datetime(date_raw)
        return dt.isoformat()
    except Exception:
        return date_raw
