"""
calendar_writer.py — Crea eventos en Google Calendar (AUTOVIEW).

Recibe ExtractedEvent y los inserta en el calendario configurado.
"""
from __future__ import annotations

from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from loguru import logger

from .config import config
from .event_extractor import ExtractedEvent


def get_calendar_service(creds: Credentials):
    """Crea el cliente de Google Calendar API."""
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def create_event(creds: Credentials, event: ExtractedEvent) -> Optional[str]:
    """
    Crea un evento en Google Calendar.

    Args:
        creds: Credenciales OAuth2 válidas.
        event: Evento extraído del correo.

    Returns:
        ID del evento creado, o None si falla.
    """
    try:
        service = get_calendar_service(creds)
    except HttpError as e:
        logger.error(f"Error conectando a Calendar: {e}")
        return None

    body = event.to_calendar_body()

    # Añadir metadata de origen al description
    source_note = f"\n\n---\nDetectado automáticamente del correo: '{event.source_subject}'"
    body["description"] = (body.get("description", "") or "") + source_note

    try:
        created = (
            service.events()
            .insert(calendarId=config.calendar_id, body=body)
            .execute()
        )
        event_id = created.get("id")
        event_link = created.get("htmlLink", "")
        logger.info(
            f"Evento creado: '{event.title}' "
            f"| ID: {event_id} "
            f"| Link: {event_link}"
        )
        return event_id
    except HttpError as e:
        logger.error(f"Error creando evento '{event.title}': {e}")
        return None


def delete_event(creds: Credentials, event_id: str) -> bool:
    """
    Elimina un evento de Google Calendar.

    Args:
        creds: Credenciales OAuth2 válidas.
        event_id: ID del evento en Google Calendar.

    Returns:
        True si se eliminó correctamente, False si falló.
    """
    try:
        service = get_calendar_service(creds)
        service.events().delete(
            calendarId=config.calendar_id,
            eventId=event_id,
        ).execute()
        logger.info(f"Evento eliminado de Calendar: {event_id}")
        return True
    except HttpError as e:
        logger.error(f"Error eliminando evento {event_id}: {e}")
        return False


def list_upcoming_events(creds: Credentials, max_results: int = 10) -> list[dict]:
    """
    Lista próximos eventos (útil para debug / verificar).

    Returns:
        Lista de eventos en formato dict de la API.
    """
    try:
        service = get_calendar_service(creds)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        result = (
            service.events()
            .list(
                calendarId=config.calendar_id,
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return result.get("items", [])
    except HttpError as e:
        logger.error(f"Error listando eventos: {e}")
        return []
