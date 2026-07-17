#!/usr/bin/env python3
"""
main.py — Orquestador principal de AUTOVIEW.

Flujo:
1. Autenticar con Google (OAuth2)
2. Leer correos de Gmail (filtrados)
3. Para cada correo no procesado:
   a. Extraer evento con LLM
   b. Si hay evento → crear en Google Calendar
   c. Marcar como procesado en SQLite
4. Mostrar resumen

Uso:
    python main.py              # ejecución normal
    python main.py --dry-run   # no crea eventos, solo detecta
    python main.py --stats     # muestra estadísticas y sale
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Asegurar que src/ esté en el path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from loguru import logger

from src.auth import get_credentials
from src.calendar_writer import create_event
from src.config import config
from src.event_extractor import extract_event
from src.gmail_reader import fetch_emails
from src.state import init_db, is_processed, mark_processed, get_stats
from src.telegram_reporter import send_report


def setup_logging() -> None:
    """Configura loguru con color y formato."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=config.log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | <cyan>{message}</cyan>",
        colorize=True,
    )
    # También a archivo
    log_file = config.db_path.parent / "app.log"
    logger.add(
        log_file,
        level="DEBUG",
        rotation="5 MB",
        retention="10 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}",
    )


def run(dry_run: bool = False) -> int:
    """
    Ejecuta el ciclo completo.

    Returns:
        Número de eventos creados.
    """
    # 0. Validar config
    errors = config.validate()
    if errors:
        for e in errors:
            logger.error(e)
        logger.error("Config incompleta. Ver docs/SETUP_GOOGLE.md y config/.env")
        return 0

    # 1. Inicializar DB
    init_db()

    # 2. Autenticar
    logger.info("Autenticando con Google...")
    creds = get_credentials()
    if not creds:
        logger.error("No se pudieron obtener credenciales. Abortando.")
        return 0
    logger.success("Autenticación OK")

    # 3. Leer correos
    logger.info(f"Buscando correos con query: {config.gmail_query}")
    emails = fetch_emails(creds)
    if not emails:
        logger.info("No hay correos nuevos para procesar")
        return 0

    # 4. Procesar cada correo
    events_created = 0
    skipped = 0
    for email in emails:
        # Saltar si ya fue procesado
        if is_processed(email.id):
            skipped += 1
            continue

        logger.info(f"Procesando: '{email.subject}' de {email.sender}")

        # Extraer evento con LLM
        event = extract_event(email)

        if event is None:
            # No hay evento, marcar como procesado sin evento
            mark_processed(
                email_id=email.id,
                thread_id=email.thread_id,
                subject=email.subject,
                sender=email.sender,
                has_event=False,
                status="processed",
            )
            continue

        # Hay evento — crear en Calendar (a menos que sea dry-run)
        if dry_run:
            logger.info(
                f"[DRY-RUN] Evento detectado: '{event.title}' "
                f"el {event.start} — NO se creó"
            )
            mark_processed(
                email_id=email.id,
                thread_id=email.thread_id,
                subject=email.subject,
                sender=email.sender,
                has_event=True,
                event_title=event.title,
                event_start=event.start,
                status="skipped",
            )
            continue

        event_id = create_event(creds, event)
        if event_id:
            events_created += 1
            mark_processed(
                email_id=email.id,
                thread_id=email.thread_id,
                subject=email.subject,
                sender=email.sender,
                has_event=True,
                event_id=event_id,
                event_title=event.title,
                event_start=event.start,
                status="processed",
            )
        else:
            logger.error(f"Fallo creando evento para email {email.id}")
            mark_processed(
                email_id=email.id,
                thread_id=email.thread_id,
                subject=email.subject,
                sender=email.sender,
                has_event=True,
                status="error",
            )

    # 5. Resumen
    stats = get_stats()
    logger.info(
        f"Resumen — Correos: {len(emails)} | "
        f"Ya procesados: {skipped} | "
        f"Eventos creados: {events_created} | "
        f"Total histórico: {stats['total_processed']} procesados, "
        f"{stats['events_created']} eventos, {stats['errors']} errores"
    )
    return events_created


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AUTOVIEW: detecta eventos en Gmail y los guarda en Google Calendar"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detecta eventos pero NO los crea en Calendar",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Muestra estadísticas y sale",
    )
    parser.add_argument(
        "--telegram-report",
        type=int,
        nargs="?",
        const=4,
        metavar="DAYS",
        help="Envía reporte de los últimos N días (default: 4) a Telegram y sale",
    )
    args = parser.parse_args()

    setup_logging()

    if args.telegram_report is not None:
        init_db()
        days = args.telegram_report
        logger.info(f"Enviando reporte de {days} días a Telegram...")
        success = send_report(days=days)
        if success:
            logger.success("Reporte enviado ✅")
        else:
            logger.error("No se pudo enviar el reporte ❌")
            sys.exit(1)
        return

    if args.stats:
        init_db()
        stats = get_stats()
        print(f"\n📊 Estadísticas de AUTOVIEW:")
        print(f"   Correos procesados (total): {stats['total_processed']}")
        print(f"   Eventos creados:             {stats['events_created']}")
        print(f"   Errores:                     {stats['errors']}")
        return

    logger.info("=== AUTOVIEW iniciando ===")
    if args.dry_run:
        logger.warning("MODO DRY-RUN — no se crearán eventos")

    try:
        run(dry_run=args.dry_run)
    except KeyboardInterrupt:
        logger.warning("Interrumpido por el usuario")
    except Exception as e:
        logger.exception(f"Error fatal: {e}")
        sys.exit(1)

    logger.info("=== Fin ===")


if __name__ == "__main__":
    main()
