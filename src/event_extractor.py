"""
event_extractor.py — Usa un LLM para detectar eventos en correos (AUTOVIEW).

El LLM recibe el texto del correo y devuelve JSON estructurado:
{
  "is_event": true,
  "title": "Examen final de Cálculo",
  "start": "2026-12-15T10:00:00",
  "end": "2026-12-15T12:00:00",  // opcional
  "location": "Aula 301",         // opcional
  "description": "..."
}

Si no hay evento → {"is_event": false}

Soporta Ollama (local, gratis), OpenAI y Gemini.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from loguru import logger

from .config import config
from .gmail_reader import EmailMessage


@dataclass
class ExtractedEvent:
    """Evento detectado en un correo, listo para crear en Calendar."""
    title: str
    start: str  # ISO 8601
    end: Optional[str]
    location: Optional[str]
    description: str
    source_email_id: str
    source_subject: str

    def to_calendar_body(self) -> dict:
        """Convierte a formato que espera Google Calendar API."""
        body = {
            "summary": self.title,
            "start": {
                "dateTime": self.start,
                "timeZone": config.timezone,
            },
            "description": self.description,
        }
        if self.end:
            body["end"] = {"dateTime": self.end, "timeZone": config.timezone}
        else:
            # Si no hay end, asumir 1 hora
            try:
                start_dt = datetime.fromisoformat(self.start)
                end_dt = start_dt.replace(microsecond=0)
                # Sumar 1 hora
                from datetime import timedelta
                end_iso = (start_dt + timedelta(hours=1)).isoformat()
                body["end"] = {"dateTime": end_iso, "timeZone": config.timezone}
            except Exception:
                body["end"] = body["start"]

        if self.location:
            body["location"] = self.location
        return body


# Prompt del sistema — instrucciones claras para el LLM
SYSTEM_PROMPT = """Eres un asistente que detecta eventos universitarios y fechas importantes en correos.

Analiza el correo y extrae eventos si los hay (exámenes, entregas, reuniones, plazos, etc.).

Reglas:
1. Si NO hay ningún evento o fecha importante, responde exactamente: {"is_event": false}
2. Si hay evento, responde en JSON válido con estos campos:
   {
     "is_event": true,
     "title": "Título corto y descriptivo del evento",
     "start": "fecha-hora en formato ISO 8601 (YYYY-MM-DDTHH:MM:SS)",
     "end": "fecha-hora de fin en ISO 8601, o null si no se menciona",
     "location": "lugar mencionado, o null",
     "description": "descripción breve del evento"
   }
3. Si el correo menciona solo una fecha sin hora, usa T09:00:00 como default.
4. Si menciona "todo el día", usa solo fecha sin hora: "YYYY-MM-DD".
5. Infiere el año si no se menciona (usa el año actual).
6. NO inventes información que no esté en el correo.
7. Responde SOLO con el JSON, sin texto adicional ni markdown.

Ejemplos:
Correo: "El examen parcial será el viernes 15 de diciembre a las 10am en el aula 301"
Respuesta: {"is_event": true, "title": "Examen parcial", "start": "2026-12-15T10:00:00", "end": "2026-12-15T12:00:00", "location": "Aula 301", "description": "Examen parcial"}

Correo: "Recuerden traer su libro de texto la próxima clase"
Respuesta: {"is_event": false}
"""


def extract_event(email: EmailMessage) -> Optional[ExtractedEvent]:
    """
    Usa el LLM para detectar si el correo contiene un evento.

    Returns:
        ExtractedEvent si detecta uno, None si no hay evento o hay error.
    """
    # Construir el prompt del usuario con el contenido del correo
    user_prompt = (
        f"Asunto: {email.subject}\n"
        f"Remitente: {email.sender}\n"
        f"Fecha del correo: {email.date}\n\n"
        f"Contenido:\n{email.body_text}\n\n"
        f"Extrae el evento si existe."
    )

    try:
        raw_response = _call_llm(user_prompt)
        event_data = _parse_llm_response(raw_response)
    except Exception as e:
        logger.error(f"Error llamando al LLM para email {email.id}: {e}")
        return None

    if not event_data or not event_data.get("is_event", False):
        logger.debug(f"Email {email.id} — sin evento detectado")
        return None

    # Validar campos mínimos
    title = event_data.get("title", "").strip()
    start = event_data.get("start", "").strip()
    if not title or not start:
        logger.warning(f"Email {email.id} — evento incompleto: title={title!r} start={start!r}")
        return None

    logger.info(f"Email {email.id} → evento detectado: '{title}' el {start}")
    return ExtractedEvent(
        title=title,
        start=start,
        end=event_data.get("end"),
        location=event_data.get("location"),
        description=event_data.get("description", ""),
        source_email_id=email.id,
        source_subject=email.subject,
    )


def _call_llm(user_prompt: str) -> str:
    """Llama al LLM configurado y retorna la respuesta."""
    if config.llm_provider == "ollama":
        return _call_ollama(user_prompt)
    elif config.llm_provider in ("openai", "openrouter"):
        return _call_openai(user_prompt)
    elif config.llm_provider == "gemini":
        return _call_gemini(user_prompt)
    else:
        raise ValueError(f"LLM_PROVIDER no soportado: {config.llm_provider}")


def _call_ollama(user_prompt: str) -> str:
    """Llama a Ollama local."""
    import ollama

    client = ollama.Client(host=config.ollama_host)
    response = client.chat(
        model=config.ollama_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        options={"temperature": 0.1, "num_predict": 300},
    )
    return response["message"]["content"]


def _call_openai(user_prompt: str) -> str:
    """Llama a API compatible con OpenAI (OpenAI directo, OpenRouter, etc.)."""
    from openai import OpenAI

    client = OpenAI(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
    )
    response = client.chat.completions.create(
        model=config.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=300,
    )
    return response.choices[0].message.content or ""


def _call_gemini(user_prompt: str) -> str:
    """Llama a Gemini API usando google.genai SDK con retry ante cuota."""
    from google import genai
    from google.genai import errors as genai_errors

    client = genai.Client(api_key=config.gemini_api_key)

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=config.gemini_model,
                contents=user_prompt,
                config={
                    "system_instruction": SYSTEM_PROMPT,
                    "temperature": 0.1,
                    "max_output_tokens": 300,
                },
            )
            return response.text or ""
        except genai_errors.ClientError as e:
            # 429 = cuota excedida — esperar y reintentar
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e).upper():
                if attempt < max_retries:
                    sleep_secs = 2 ** attempt  # backoff exponencial: 2, 4, 8, 16...
                    logger.warning(
                        f"Cuota Gemini excedida, reintento {attempt}/{max_retries} "
                        f"en {sleep_secs}s..."
                    )
                    time.sleep(sleep_secs)
                    continue
            raise  # no reintentar otros errores
    return ""


def _parse_llm_response(raw: str) -> Optional[dict]:
    """Parsea la respuesta del LLM como JSON (tolerante a markdown)."""
    raw = raw.strip()
    # Quitar markdown code fences si los hay
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1] if "\n" in raw else raw
        raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"Respuesta LLM no es JSON válido: {raw[:200]}")
        return None
