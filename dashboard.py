#!/usr/bin/env python3
"""
dashboard.py — Interfaz visual para AUTOVIEW (Streamlit).

Monitorea, controla y administra todo lo que AUTOVIEW procesa:
- Estadísticas en tiempo real
- CRUD completo de emails procesados
- Gestión manual de eventos en Google Calendar
- Visor de logs
- Ejecución manual de AUTOVIEW

Uso: streamlit run dashboard.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st
import pandas as pd

# Asegurar que src/ esté en el path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# ─── Módulos de AUTOVIEW ──────────────────────────────────────────
from src.auth import get_credentials
from src.calendar_writer import create_event, delete_event, list_upcoming_events
from src.config import config
from src.event_extractor import ExtractedEvent
from src.state import (
    init_db,
    get_stats,
    get_all_emails,
    get_email_by_id,
    update_email_record,
    delete_email_record,
    get_timeline_stats,
    get_sender_stats,
    mark_processed,
)

# ─── Configuración de la página ────────────────────────────────────
st.set_page_config(
    page_title="AUTOVIEW Dashboard",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Inicializar DB y estado ───────────────────────────────────────
init_db()

if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False
if "creds" not in st.session_state:
    st.session_state.creds = None
if "selected_email" not in st.session_state:
    st.session_state.selected_email = None
if "run_output" not in st.session_state:
    st.session_state.run_output = ""
if "run_status" not in st.session_state:
    st.session_state.run_status = None
if "page" not in st.session_state:
    st.session_state.page = "🏠 Inicio"


# ─── Autenticación Google ─────────────────────────────────────────
@st.dialog("🔐 Autenticación Google")
def auth_dialog():
    st.markdown(
        "Necesitas autenticarte con Google para que el dashboard pueda "
        "leer/crear/eliminar eventos en Calendar."
    )
    if st.button("Autenticar con Google", type="primary", use_container_width=True):
        with st.spinner("Abriendo navegador para autenticación..."):
            creds = get_credentials()
            if creds:
                st.session_state.creds = creds
                st.session_state.auth_ok = True
                st.success("✅ Autenticación exitosa")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Falló la autenticación")


def ensure_auth():
    """Verifica auth, si no, muestra diálogo."""
    if not st.session_state.auth_ok or not st.session_state.creds:
        auth_dialog()
        return False
    # Refrescar token si expiró
    creds = st.session_state.creds
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        st.session_state.creds = creds
    return True


# ─── Helpers de Calendar ──────────────────────────────────────────
def calendar_create_event(title: str, start_dt: str, end_dt: str | None,
                          location: str | None, description: str) -> str | None:
    """Crea un evento en Google Calendar y retorna su ID."""
    if not ensure_auth():
        return None
    event = ExtractedEvent(
        title=title,
        start=start_dt,
        end=end_dt,
        location=location,
        description=description,
        source_email_id="manual",
        source_subject="Creado desde dashboard",
    )
    return create_event(st.session_state.creds, event)


def calendar_delete_event(event_id: str) -> bool:
    """Elimina un evento de Google Calendar."""
    if not ensure_auth():
        return False
    return delete_event(st.session_state.creds, event_id)


def calendar_list_upcoming(max_results: int = 20) -> list[dict]:
    """Lista próximos eventos desde Calendar."""
    if not ensure_auth():
        return []
    return list_upcoming_events(st.session_state.creds, max_results)


# ─── Sidebar ──────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        logo_path = PROJECT_ROOT / "assets" / "logo.png"
        if logo_path.exists():
            st.image(str(logo_path), width=60)
        else:
            st.image("https://img.icons8.com/fluency/96/calendar--v4.png", width=60)
        st.title("AUTOVIEW")
        st.caption("Control Panel")

        # Estado de auth
        if st.session_state.auth_ok:
            st.success("✅ Google conectado")
        else:
            st.warning("🔒 Google desconectado")
            if st.button("🔐 Autenticar"):
                auth_dialog()

        st.divider()

        # Navegación
        pages = {
            "🏠 Inicio": "🏠 Inicio",
            "📧 Emails": "📧 Emails",
            "📅 Calendar": "📅 Calendar",
            "➕ Añadir Evento": "➕ Añadir Evento",
            "📋 Logs": "📋 Logs",
            "▶️ Ejecutar": "▶️ Ejecutar",
        }
        for emoji, page_name in pages.items():
            if st.sidebar.button(
                emoji,
                use_container_width=True,
                type="secondary" if st.session_state.page != page_name else "primary",
                key=f"nav_{page_name}",
            ):
                st.session_state.page = page_name
                st.rerun()

        st.divider()
        st.caption(f"Último acceso: {datetime.now():%H:%M:%S}")


# ─── Páginas ──────────────────────────────────────────────────────

def page_home():
    st.header("🏠 Panel de Control")

    # Stats cards
    stats = get_stats()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📬 Correos Procesados", stats["total_processed"])
    with col2:
        st.metric("📅 Eventos Creados", stats["events_created"])
    with col3:
        st.metric("❌ Errores", stats["errors"])
    with col4:
        tasa = 0
        if stats["total_processed"] > 0:
            tasa = round(stats["events_created"] / stats["total_processed"] * 100, 1)
        st.metric("🎯 Tasa de Eventos", f"{tasa}%")

    # Timeline chart
    st.subheader("📈 Actividad (últimos 30 días)")
    timeline = get_timeline_stats(30)
    if timeline:
        df = pd.DataFrame(timeline)
        df["day"] = pd.to_datetime(df["day"])
        df = df.sort_values("day")

        tab1, tab2 = st.tabs(["📊 Procesados por día", "📊 Eventos vs Errores"])
        with tab1:
            st.bar_chart(df.set_index("day")["total"])
        with tab2:
            st.bar_chart(df.set_index("day")[["events", "errors"]])
    else:
        st.info("Sin datos en los últimos 30 días")

    # Sender stats
    st.subheader("✉️ Top Remitentes")
    senders = get_sender_stats()
    if senders:
        df_s = pd.DataFrame(senders)
        st.dataframe(
            df_s.rename(columns={
                "sender": "Remitente",
                "total": "Correos",
                "events": "Eventos",
                "errors": "Errores",
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Sin datos de remitentes")

    # Actividad reciente
    st.subheader("🕐 Actividad Reciente")
    from src.state import get_recent
    recent = get_recent(10)
    if recent:
        df_r = pd.DataFrame(recent)
        cols = {
            "subject": "Asunto",
            "sender": "Remitente",
            "processed_at": "Fecha",
            "status": "Estado",
        }
        display = df_r[list(cols.keys())].rename(columns=cols)
        display["Fecha"] = pd.to_datetime(display["Fecha"]).dt.strftime("%d/%m %H:%M")
        st.dataframe(display, use_container_width=True, hide_index=True)
    else:
        st.info("No hay actividad registrada")


def page_emails():
    st.header("📧 Correos Procesados")

    # Si hay un email seleccionado, mostrar detalle
    if st.session_state.selected_email:
        show_email_detail()
        return

    # Filtros
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search = st.text_input("🔍 Buscar por asunto o evento", key="search_emails")
    with col2:
        status_filter = st.selectbox(
            "Estado",
            ["Todos", "processed", "error", "skipped"],
            key="status_filter",
        )
    with col3:
        per_page = st.selectbox("Por página", [20, 50, 100], index=0, key="per_page")

    # Paginación
    if "page_num" not in st.session_state:
        st.session_state.page_num = 0

    offset = st.session_state.page_num * per_page
    sf = status_filter if status_filter != "Todos" else None
    emails, total = get_all_emails(
        limit=per_page, offset=offset,
        status_filter=sf, search=search if search else None,
    )

    # Info de paginación
    total_pages = max(1, (total + per_page - 1) // per_page)
    st.caption(f"Mostrando {offset + 1}–{min(offset + per_page, total)} de {total} registros")

    if not emails:
        st.info("No hay correos que coincidan con los filtros")
        return

    # Tabla
    df = pd.DataFrame(emails)
    display_cols = {
        "subject": "Asunto",
        "sender": "Remitente",
        "processed_at": "Procesado",
        "has_event": "Evento",
        "event_title": "Título del Evento",
        "status": "Estado",
    }
    df_display = df[list(display_cols.keys())].rename(columns=display_cols)
    df_display["Evento"] = df_display["Evento"].apply(lambda x: "✅" if x else "❌")
    df_display["Procesado"] = pd.to_datetime(df_display["Procesado"]).dt.strftime("%d/%m %H:%M")

    # Columnas con colores en estado
    def style_status(v):
        colors = {"processed": "green", "error": "red", "skipped": "orange"}
        c = colors.get(v, "gray")
        return f'<span style="color:{c};font-weight:bold">{v}</span>'

    # Mostrar tabla clickeable
    for idx, row in df.iterrows():
        col_a, col_b = st.columns([5, 1])
        with col_a:
            st.markdown(
                f"**{row['subject'][:80]}**  ·  {row['sender'][:40]}  ·  "
                f"{style_status(row['status'])}",
                unsafe_allow_html=True,
            )
        with col_b:
            if st.button("👁️ Ver", key=f"view_{row['email_id']}"):
                st.session_state.selected_email = row["email_id"]
                st.rerun()

    # Paginación
    col1, col2, col3, _ = st.columns([1, 1, 1, 3])
    with col1:
        if st.button("⬅ Anterior", disabled=st.session_state.page_num <= 0):
            st.session_state.page_num -= 1
            st.rerun()
    with col2:
        st.caption(f"Pág. {st.session_state.page_num + 1} de {total_pages}")
    with col3:
        if st.button("Siguiente ➡", disabled=st.session_state.page_num >= total_pages - 1):
            st.session_state.page_num += 1
            st.rerun()


def show_email_detail():
    """Muestra el detalle de un email con opciones de edición/eliminación."""
    email_id = st.session_state.selected_email
    record = get_email_by_id(email_id)

    if not record:
        st.error("Registro no encontrado")
        st.session_state.selected_email = None
        st.rerun()
        return

    st.button("⬅ Volver a lista", on_click=lambda: setattr(
        st.session_state, "selected_email", None
    ))

    st.subheader(f"📧 {record['subject']}")

    # Info general
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Email ID:** `{record['email_id']}`")
        st.markdown(f"**Thread ID:** `{record['thread_id'] or '—'}`")
        st.markdown(f"**Remitente:** {record['sender']}")
    with col2:
        st.markdown(f"**Procesado:** {record['processed_at']}")
        st.markdown(f"**Estado:** `{record['status']}`")
        st.markdown(f"**Tiene evento:** {'✅ Sí' if record['has_event'] else '❌ No'}")

    # Evento asociado
    st.divider()
    st.subheader("📅 Evento Asociado")

    if record["has_event"] and record["event_title"]:
        with st.form(key=f"edit_event_{email_id}"):
            new_title = st.text_input("Título del evento", value=record["event_title"] or "")
            new_start = st.text_input("Fecha inicio (ISO 8601)", value=record["event_start"] or "")
            new_status = st.selectbox(
                "Estado",
                ["processed", "error", "skipped"],
                index=["processed", "error", "skipped"].index(record["status"]),
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("💾 Guardar cambios", type="primary", use_container_width=True):
                    update_email_record(
                        email_id,
                        event_title=new_title,
                        event_start=new_start,
                        status=new_status,
                    )
                    st.success("✅ Cambios guardados")
                    time.sleep(0.5)
                    st.rerun()

            with col2:
                if record.get("event_id"):
                    if st.form_submit_button("🗑️ Eliminar de Calendar + DB", type="secondary", use_container_width=True):
                        if ensure_auth():
                            ok = calendar_delete_event(record["event_id"])
                            if ok or True:  # aunque falle en Calendar, eliminar de DB
                                delete_email_record(email_id)
                                st.success("✅ Eliminado de Calendar y DB")
                                st.session_state.selected_email = None
                                time.sleep(0.5)
                                st.rerun()
                        else:
                            st.error("Necesitas autenticarte primero")

        if record.get("event_id"):
            st.markdown(f"**Calendar ID:** `{record['event_id']}`")
            st.markdown(
                f'🔗 [Abrir en Google Calendar](https://calendar.google.com/calendar/u/0/r/eventedit/{record["event_id"]})'
            )
    else:
        st.info("Este correo no tiene un evento asociado")
        if st.button("🗑️ Eliminar registro"):
            delete_email_record(email_id)
            st.session_state.selected_email = None
            st.rerun()


def page_calendar():
    st.header("📅 Google Calendar")

    if not ensure_auth():
        st.warning("Autentícate con Google para ver el calendario")
        return

    # Refresh button
    col1, col2 = st.columns([4, 1])
    with col1:
        st.subheader("📅 Próximos Eventos")
    with col2:
        if st.button("🔄 Refrescar", use_container_width=True):
            st.rerun()

    events = calendar_list_upcoming(20)
    if events:
        for ev in events:
            start = ev.get("start", {})
            start_str = start.get("dateTime", start.get("date", "?"))
            try:
                dt = datetime.fromisoformat(start_str)
                start_str = dt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                pass

            with st.expander(f"**{ev.get('summary', 'Sin título')}** — {start_str}"):
                st.markdown(f"**ID:** `{ev.get('id', '?')}`")
                st.markdown(f"**Link:** [Abrir]({ev.get('htmlLink', '#')})")
                desc = ev.get("description", "")
                if desc:
                    st.markdown(f"**Descripción:** {desc[:500]}")
    else:
        st.info("No hay próximos eventos en el calendario")

    # También mostrar eventos desde la DB local
    st.divider()
    st.subheader("📊 Eventos en DB Local (próximos)")
    from src.state import get_events_by_date_range
    today = datetime.now().isoformat()
    next_month = (datetime.now() + timedelta(days=60)).isoformat()
    db_events = get_events_by_date_range(today, next_month)
    if db_events:
        df = pd.DataFrame(db_events)
        st.dataframe(
            df.rename(columns={
                "subject": "Asunto",
                "sender": "Remitente",
                "event_title": "Evento",
                "event_start": "Fecha",
                "status": "Estado",
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No hay eventos próximos registrados en la DB")


def page_add_event():
    st.header("➕ Añadir Evento Manual")

    if not ensure_auth():
        st.warning("Necesitas autenticarte con Google para crear eventos")
        return

    with st.form("add_event_form", clear_on_submit=True):
        st.subheader("Nuevo Evento")
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Título del evento *", placeholder="Ej: Examen de Cálculo")
            start_date = st.date_input("Fecha de inicio *", value=datetime.now())
            start_time = st.time_input("Hora de inicio *", value=datetime.now().replace(hour=9, minute=0))
        with col2:
            location = st.text_input("Lugar (opcional)", placeholder="Ej: Aula 301")
            end_date = st.date_input("Fecha de fin", value=None)
            end_time = st.time_input("Hora de fin", value=None)

        description = st.text_area("Descripción", placeholder="Detalles del evento...")
        st.caption("* Campos obligatorios")

        submitted = st.form_submit_button("📅 Crear Evento", type="primary", use_container_width=True)

        if submitted:
            if not title.strip():
                st.error("El título es obligatorio")
                return

            start_dt = datetime.combine(start_date, start_time).isoformat()
            end_dt = None
            if end_date and end_time:
                end_dt = datetime.combine(end_date, end_time).isoformat()
            elif end_date:
                end_dt = datetime.combine(end_date, start_time).isoformat()

            with st.spinner("Creando evento en Google Calendar..."):
                event_id = calendar_create_event(
                    title=title.strip(),
                    start_dt=start_dt,
                    end_dt=end_dt,
                    location=location.strip() or None,
                    description=description.strip(),
                )

            if event_id:
                # Guardar en DB local también
                fake_id = f"manual_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
                mark_processed(
                    email_id=fake_id,
                    thread_id="",
                    subject=f"[Manual] {title.strip()}",
                    sender="dashboard",
                    has_event=True,
                    event_id=event_id,
                    event_title=title.strip(),
                    event_start=start_dt,
                    status="processed",
                )
                st.success(f"✅ Evento creado: {title}")
                st.markdown(f"🔗 [Ver en Calendar](https://calendar.google.com/calendar/u/0/r/eventedit/{event_id})")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ No se pudo crear el evento. Revisa los logs.")


def page_logs():
    st.header("📋 Logs")
    log_file = config.db_path.parent / "app.log"

    # Auto-refresh
    auto = st.checkbox("Auto-refresh (cada 5s)", value=False)
    col1, col2 = st.columns([3, 1])
    with col1:
        lines = st.slider("Líneas a mostrar", 50, 500, 200)
    with col2:
        if st.button("🔄 Refrescar", use_container_width=True):
            st.rerun()

    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        last_lines = all_lines[-lines:]
        st.code("".join(last_lines), language="log")

        st.caption(f"Mostrando últimas {len(last_lines)} líneas de {len(all_lines)} totales")
    else:
        st.warning(f"No se encontró {log_file}")

    if auto:
        time.sleep(5)
        st.rerun()


def page_run():
    st.header("▶️ Ejecutar AUTOVIEW")

    st.markdown(
        "Ejecuta el ciclo completo de AUTOVIEW manualmente desde aquí."
    )

    col1, col2 = st.columns(2)
    with col1:
        dry_run = st.checkbox("Modo dry-run (no crear eventos)")
    with col2:
        st.write("")  # spacer

    if st.button(
        "🚀 Ejecutar AUTOVIEW ahora",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.run_status == "running",
    ):
        st.session_state.run_status = "running"
        st.session_state.run_output = ""
        st.rerun()

    # Ejecutar en background (simulado con subprocess)
    if st.session_state.run_status == "running":
        with st.spinner("Ejecutando AUTOVIEW..."):
            cmd = [sys.executable, "main.py"]
            if dry_run:
                cmd.append("--dry-run")
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(PROJECT_ROOT),
                )
                output = result.stdout + "\n" + result.stderr
                st.session_state.run_output = output
                st.session_state.run_status = "done"
            except subprocess.TimeoutExpired:
                st.session_state.run_output = "⏱️ Timeout: la ejecución tomó más de 2 minutos"
                st.session_state.run_status = "error"
            except Exception as e:
                st.session_state.run_output = f"❌ Error: {e}"
                st.session_state.run_status = "error"
        st.rerun()

    # Mostrar output
    if st.session_state.run_output:
        st.subheader("📤 Output")
        st.code(st.session_state.run_output, language="log")

        if st.session_state.run_status == "done":
            st.success("✅ Ejecución completada")
        elif st.session_state.run_status == "error":
            st.error("❌ Error en la ejecución")

        if st.button("🗑️ Limpiar output"):
            st.session_state.run_output = ""
            st.session_state.run_status = None
            st.rerun()


# ─── Main ─────────────────────────────────────────────────────────
def main():
    render_sidebar()

    # Routing
    pages = {
        "🏠 Inicio": page_home,
        "📧 Emails": page_emails,
        "📅 Calendar": page_calendar,
        "➕ Añadir Evento": page_add_event,
        "📋 Logs": page_logs,
        "▶️ Ejecutar": page_run,
    }
    page_func = pages.get(st.session_state.page, page_home)
    page_func()


if __name__ == "__main__":
    main()
