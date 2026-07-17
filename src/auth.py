"""
auth.py — Autenticación OAuth2 con Google (AUTOVIEW).

Maneja el flujo de OAuth2 para Gmail y Calendar.
La primera vez abre el navegador; después usa el token guardado.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from loguru import logger

from .config import config

# Scopes necesarios (read-only Gmail, read-write Calendar events)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


def get_credentials() -> Optional[Credentials]:
    """
    Obtiene credenciales OAuth2 válidas.

    Flujo:
    1. Si existe token.json y es válido → lo usa.
    2. Si existe pero expiró → lo refresca.
    3. Si no existe → abre navegador para autorizar.

    Returns:
        Credentials o None si falla.
    """
    creds = None
    token_path: Path = config.token_file
    creds_path: Path = config.credentials_file

    # 1. Intentar cargar token existente
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            logger.debug(f"Token cargado de {token_path}")
        except Exception as e:
            logger.warning(f"Token corrupto, se regenerará: {e}")
            creds = None

    # 2. Si no hay creds o expiraron, refrescar
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds, token_path)
            logger.info("Token refrescado correctamente")
        except Exception as e:
            logger.error(f"Error refrescando token: {e}")
            return None

    # 3. Si no hay creds, flujo OAuth completo (abre navegador)
    if not creds or not creds.valid:
        if not creds_path.exists():
            logger.error(
                f"No existe {creds_path}. Ver docs/SETUP_GOOGLE.md"
            )
            return None

        try:
            logger.info("Iniciando flujo OAuth — se abrirá el navegador")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(creds_path), SCOPES
            )
            creds = flow.run_local_server(port=0)  # puerto aleatorio
            _save_token(creds, token_path)
            logger.info("Autorización exitosa — token guardado")
        except Exception as e:
            logger.error(f"Error en flujo OAuth: {e}")
            return None

    return creds


def _save_token(creds: Credentials, path: Path) -> None:
    """Guarda el token en disco (permisos 600)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(creds.to_json())
    path.chmod(0o600)  # solo el owner puede leer
    logger.debug(f"Token guardado en {path}")


def revoke_credentials() -> None:
    """Borra el token local (no revoca en servidor). Útil para re-autenticar."""
    if config.token_file.exists():
        config.token_file.unlink()
        logger.info("Token local borrado — se volverá a pedir autorización")
