#!/usr/bin/env python3
"""
app.py — WebUI Unificada (Streamlit)
Un solo panel en localhost:8501 con 6 pestañas:
🏠 Home | 📬 AUTOVIEW | 🗣️ JARVIS | 📅 Agenda | 📊 Sistema | ⚙️ Acciones

Dependencias: streamlit, pandas, psutil, requests, google-api-python-client, python-dotenv
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import psutil
import requests
import streamlit as st
import yaml  # movido al tope (estaba dentro de un loop)

# ─── Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# ─── Configuración de página ────────────────────────────────────────────
st.set_page_config(
    page_title="WebUI Unificada",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Estado global ──────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "🏠 Home"
if "jarvis_history" not in st.session_state:
    st.session_state.jarvis_history = []
if "jarvis_connected" not in st.session_state:
    st.session_state.jarvis_connected = False
if "autoview_auth_ok" not in st.session_state:
    st.session_state.autoview_auth_ok = False
if "autoview_creds" not in st.session_state:
    st.session_state.autoview_creds = None
if "timeline_events" not in st.session_state:
    st.session_state.timeline_events = []

# ─── Constantes ─────────────────────────────────────────────────────────
JARVIS_API = os.getenv("JARVIS_API", "http://localhost:5000")
SCHOOL_API = os.getenv("SCHOOL_API", "http://localhost:8000")
VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT", "/home/aaronsoto/OBSIIDIAN/Aaron_segundo_cerebro"))

# ─── Helpers ────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_timeline(event: str, source: str, level: str = "info"):
    """Añade evento al timeline cross-proyecto."""
    st.session_state.timeline_events.insert(0, {
        "time": datetime.now().strftime("%H:%M:%S"),
        "event": event,
        "source": source,
        "level": level,
    })
    if len(st.session_state.timeline_events) > 100:
        st.session_state.timeline_events = st.session_state.timeline_events[:100]


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int = 30) -> tuple[int, str, str]:
    """Ejecuta comando y retorna (code, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=str(cwd or PROJECT_ROOT)
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Timeout ({timeout}s)"
    except Exception as e:
        return -1, "", str(e)


# ─── Sidebar ────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/home-automation.png", width=60)
        st.title("WebUI Unificada")
        st.caption(f"🕐 {datetime.now():%H:%M:%S}")

        # Estado de servicios
        st.divider()
        st.subheader("🔌 Servicios")

        # JARVIS
        jarvis_ok = check_jarvis()
        st.session_state.jarvis_connected = jarvis_ok
        st.markdown(f"{'🟢' if jarvis_ok else '🔴'} **JARVIS** (puerto 5000)")

        # AUTOVIEW
        autoview_ok = check_autoview_db()
        st.markdown(f"{'🟢' if autoview_ok else '🔴'} **AUTOVIEW** (DB local)")

        # School API
        school_ok = check_school_api()
        st.markdown(f"{'🟢' if school_ok else '🔴'} **School API** (puerto 8000)")

        # Vault
        vault_ok = VAULT_PATH.exists()
        st.markdown(f"{'🟢' if vault_ok else '🔴'} **Vault Obsidian**")

        st.divider()

        # Navegación
        pages = {
            "🏠 Home": "🏠 Home",
            "📬 AUTOVIEW": "📬 AUTOVIEW",
            "🗣️ JARVIS": "🗣️ JARVIS",
            "📅 Agenda": "📅 Agenda",
            "📊 Sistema": "📊 Sistema",
            "⚙️ Acciones": "⚙️ Acciones",
        }
        for emoji, page_name in pages.items():
            if st.button(
                emoji,
                use_container_width=True,
                type="primary" if st.session_state.page == page_name else "secondary",
                key=f"nav_{page_name}",
            ):
                st.session_state.page = page_name
                st.rerun()

        st.divider()
        st.caption(f"v1.0 · {datetime.now():%Y-%m-%d}")


# ─── Health checks ──────────────────────────────────────────────────────

def check_jarvis() -> bool:
    try:
        r = requests.get(f"{JARVIS_API}/status", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


_autoview_db_checked = False

def check_autoview_db() -> bool:
    global _autoview_db_checked
    if _autoview_db_checked:
        return True
    try:
        from src.state import init_db
        init_db()
        _autoview_db_checked = True
        return True
    except Exception:
        return False


def check_school_api() -> bool:
    try:
        r = requests.get(f"{SCHOOL_API}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


# ─── Página: Home ───────────────────────────────────────────────────────
def page_home():
    st.header("🏠 Panel Principal")

    # Métricas rápidas
    col1, col2, col3, col4 = st.columns(4)

    # JARVIS status
    with col1:
        jarvis_ok = st.session_state.jarvis_connected
        st.metric("🗣️ JARVIS", "Online" if jarvis_ok else "Offline", delta="🟢" if jarvis_ok else "🔴")

    # AUTOVIEW stats
    with col2:
        try:
            from src.state import get_stats
            stats = get_stats()
            st.metric("📬 Correos procesados", stats.get("total_processed", 0))
        except Exception:
            st.metric("📬 AUTOVIEW", "Error DB")

    # School API
    with col3:
        try:
            r = requests.get(f"{SCHOOL_API}/tareas/", timeout=2)
            if r.status_code == 200:
                tareas = r.json()
                pendientes = sum(1 for t in tareas if not t.get("completada"))
                st.metric("📚 Tareas pendientes", pendientes)
            else:
                st.metric("📚 School API", "Error")
        except Exception:
            st.metric("📚 School API", "Offline")

    # Sistema
    with col4:
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        st.metric("💻 CPU / RAM", f"{cpu:.0f}% / {ram:.0f}%")

    st.divider()

    # Acciones rápidas
    st.subheader("⚡ Acciones Rápidas")
    qcol1, qcol2, qcol3, qcol4 = st.columns(4)

    with qcol1:
        if st.button("🚀 Ejecutar AUTOVIEW", use_container_width=True):
            with st.spinner("Ejecutando..."):
                code, out, err = run_cmd([sys.executable, "main.py"])
                if code == 0:
                    st.success("✅ AUTOVIEW completado")
                    add_timeline("AUTOVIEW ejecutado manualmente", "AUTOVIEW", "success")
                else:
                    st.error(f"❌ Error: {err}")
                    add_timeline(f"AUTOVIEW falló: {err}", "AUTOVIEW", "error")

    with qcol2:
        if st.button("🗣️ Abrir JARVIS WebUI", use_container_width=True):
            st.markdown(f"[Abrir JARVIS]({JARVIS_API})")
            add_timeline("Abierto JARVIS WebUI", "JARVIS", "info")

    with qcol3:
        if st.button("📚 Abrir School Dashboard", use_container_width=True):
            st.markdown("[Abrir School Dashboard](http://localhost:5173)")
            add_timeline("Abierto School Dashboard", "SCHOOL", "info")

    with qcol4:
        if st.button("🔄 Sync Vault → DB", use_container_width=True):
            with st.spinner("Sincronizando..."):
                try:
                    r = requests.post(f"{SCHOOL_API}/sync/importar", timeout=30)
                    if r.status_code == 200:
                        st.success(f"✅ {r.json()}")
                        add_timeline("Sync Vault→DB completado", "SCHOOL", "success")
                    else:
                        st.error(f"❌ {r.text}")
                except Exception as e:
                    st.error(f"❌ {e}")

    st.divider()

    # Timeline cross-proyecto
    st.subheader("📜 Timeline Reciente (Cross-Proyecto)")
    if st.session_state.timeline_events:
        df = pd.DataFrame(st.session_state.timeline_events[:20])
        st.dataframe(
            df[["time", "source", "event", "level"]].rename(columns={
                "time": "Hora", "source": "Origen", "event": "Evento", "level": "Nivel"
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Sin eventos aún. Ejecuta acciones para ver timeline.")


# ─── Página: AUTOVIEW ───────────────────────────────────────────────────
def page_autoview():
    st.header("📬 AUTOVIEW — Gmail → LLM → Calendar")

    # Importar módulos de AUTOVIEW
    try:
        from src.auth import get_credentials
        from src.calendar_writer import create_event, delete_event, list_upcoming_events
        from src.config import config
        from src.event_extractor import ExtractedEvent
        from src.state import (
            init_db, get_stats, get_all_emails, get_email_by_id,
            update_email_record, delete_email_record, get_timeline_stats,
            get_sender_stats, mark_processed, get_recent, get_events_by_date_range,
        )
    except ImportError as e:
        st.error(f"❌ No se pueden importar módulos AUTOVIEW: {e}")
        return

    init_db()

    # Auth Google
    @st.dialog("🔐 Autenticación Google")
    def auth_dialog():
        st.markdown("Necesitas autenticarte con Google para leer/crear/eliminar eventos en Calendar.")
        if st.button("Autenticar con Google", type="primary", use_container_width=True):
            with st.spinner("Abriendo navegador..."):
                creds = get_credentials()
                if creds:
                    st.session_state.autoview_creds = creds
                    st.session_state.autoview_auth_ok = True
                    st.success("✅ Autenticación exitosa")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Falló la autenticación")

    def ensure_auth() -> bool:
        if not st.session_state.autoview_auth_ok or not st.session_state.autoview_creds:
            auth_dialog()
            return False
        creds = st.session_state.autoview_creds
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            st.session_state.autoview_creds = creds
        return True

    def calendar_create_event(title: str, start_dt: str, end_dt: str | None,
                              location: str | None, description: str) -> str | None:
        if not ensure_auth():
            return None
        event = ExtractedEvent(
            title=title, start=start_dt, end=end_dt, location=location,
            description=description, source_email_id="manual",
            source_subject="Creado desde WebUI Unificada",
        )
        return create_event(st.session_state.autoview_creds, event)

    def calendar_delete_event(event_id: str) -> bool:
        if not ensure_auth():
            return False
        return delete_event(st.session_state.autoview_creds, event_id)

    def calendar_list_upcoming(max_results: int = 20) -> list[dict]:
        if not ensure_auth():
            return []
        return list_upcoming_events(st.session_state.autoview_creds, max_results)

    # Sidebar state
    if st.session_state.autoview_auth_ok:
        st.sidebar.success("✅ Google conectado")
    else:
        st.sidebar.warning("🔒 Google desconectado")
        if st.sidebar.button("🔐 Autenticar"):
            auth_dialog()

    # Tabs internos
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🏠 Inicio", "📧 Emails", "📅 Calendar", "➕ Añadir Evento", "📋 Logs", "▶️ Ejecutar"
    ])

    with tab1:
        stats = get_stats()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📬 Correos Procesados", stats["total_processed"])
        c2.metric("📅 Eventos Creados", stats["events_created"])
        c3.metric("❌ Errores", stats["errors"])
        tasa = round(stats["events_created"] / stats["total_processed"] * 100, 1) if stats["total_processed"] > 0 else 0
        c4.metric("🎯 Tasa Eventos", f"{tasa}%")

        st.subheader("📈 Actividad (30 días)")
        timeline = get_timeline_stats(30)
        if timeline:
            df = pd.DataFrame(timeline)
            df["day"] = pd.to_datetime(df["day"])
            df = df.sort_values("day")
            t1, t2 = st.tabs(["📊 Procesados/día", "📊 Eventos vs Errores"])
            with t1:
                st.bar_chart(df.set_index("day")["total"])
            with t2:
                st.bar_chart(df.set_index("day")[["events", "errors"]])
        else:
            st.info("Sin datos en los últimos 30 días")

        st.subheader("✉️ Top Remitentes")
        senders = get_sender_stats()
        if senders:
            df_s = pd.DataFrame(senders)
            st.dataframe(
                df_s.rename(columns={"sender": "Remitente", "total": "Correos", "events": "Eventos", "errors": "Errores"}),
                use_container_width=True, hide_index=True,
            )

        st.subheader("🕐 Actividad Reciente")
        recent = get_recent(10)
        if recent:
            df_r = pd.DataFrame(recent)
            cols = {"subject": "Asunto", "sender": "Remitente", "processed_at": "Fecha", "status": "Estado"}
            display = df_r[list(cols.keys())].rename(columns=cols)
            display["Fecha"] = pd.to_datetime(display["Fecha"]).dt.strftime("%d/%m %H:%M")
            st.dataframe(display, use_container_width=True, hide_index=True)

    with tab2:
        if "selected_email" not in st.session_state:
            st.session_state.selected_email = None

        if st.session_state.selected_email:
            show_email_detail(st.session_state.selected_email, get_email_by_id, update_email_record,
                              delete_email_record, calendar_delete_event, ensure_auth)
            return

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            search = st.text_input("🔍 Buscar", key="search_emails")
        with col2:
            status_filter = st.selectbox("Estado", ["Todos", "processed", "error", "skipped"], key="status_filter")
        with col3:
            per_page = st.selectbox("Por página", [20, 50, 100], index=0, key="per_page")

        if "page_num" not in st.session_state:
            st.session_state.page_num = 0

        offset = st.session_state.page_num * per_page
        sf = status_filter if status_filter != "Todos" else None
        emails, total = get_all_emails(limit=per_page, offset=offset, status_filter=sf, search=search or None)

        total_pages = max(1, (total + per_page - 1) // per_page)
        st.caption(f"Mostrando {offset + 1}–{min(offset + per_page, total)} de {total}")

        if not emails:
            st.info("Sin correos que coincidan")
        else:
            df = pd.DataFrame(emails)
            for idx, row in df.iterrows():
                col_a, col_b = st.columns([5, 1])
                with col_a:
                    status_emoji = {"processed": "✅", "error": "❌", "skipped": "⏭️"}.get(row["status"], "❓")
                    st.markdown(
                        f"**{row['subject'][:80]}** · {row['sender'][:40]} · {status_emoji} `{row['status']}`"
                    )
                with col_b:
                    if st.button("👁️", key=f"view_{row['email_id']}"):
                        st.session_state.selected_email = row["email_id"]
                        st.rerun()

        c1, c2, c3, _ = st.columns([1, 1, 1, 3])
        with c1:
            if st.button("⬅ Anterior", disabled=st.session_state.page_num <= 0):
                st.session_state.page_num -= 1
                st.rerun()
        with c2:
            st.caption(f"Pág. {st.session_state.page_num + 1} de {total_pages}")
        with c3:
            if st.button("Siguiente ➡", disabled=st.session_state.page_num >= total_pages - 1):
                st.session_state.page_num += 1
                st.rerun()

    with tab3:
        if not ensure_auth():
            st.warning("Autentícate para ver el calendario")
        else:
            c1, c2 = st.columns([4, 1])
            with c1:
                st.subheader("📅 Próximos Eventos (Google Calendar)")
            with c2:
                if st.button("🔄 Refrescar"):
                    st.rerun()

            events = calendar_list_upcoming(20)
            if events:
                for ev in events:
                    start = ev.get("start", {})
                    start_str = start.get("dateTime", start.get("date", "?"))
                    try:
                        dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                        start_str = dt.strftime("%d/%m/%Y %H:%M")
                    except Exception:
                        pass
                    with st.expander(f"**{ev.get('summary', 'Sin título')}** — {start_str}"):
                        st.markdown(f"**ID:** `{ev.get('id', '?')}`")
                        st.markdown(f"**Link:** [Abrir]({ev.get('htmlLink', '#')})")
                        if ev.get("description"):
                            st.markdown(f"**Desc:** {ev['description'][:500]}")
            else:
                st.info("No hay eventos próximos")

            st.divider()
            st.subheader("📊 Eventos en DB Local (próximos 60 días)")
            today = datetime.now().isoformat()
            next_month = (datetime.now() + timedelta(days=60)).isoformat()
            db_events = get_events_by_date_range(today, next_month)
            if db_events:
                df = pd.DataFrame(db_events)
                st.dataframe(
                    df.rename(columns={"subject": "Asunto", "sender": "Remitente",
                                       "event_title": "Evento", "event_start": "Fecha", "status": "Estado"}),
                    use_container_width=True, hide_index=True,
                )

    with tab4:
        if not ensure_auth():
            st.warning("Necesitas autenticarte con Google")
        else:
            with st.form("add_event_form", clear_on_submit=True):
                st.subheader("➕ Nuevo Evento Manual")
                c1, c2 = st.columns(2)
                with c1:
                    title = st.text_input("Título *", placeholder="Ej: Examen de Cálculo")
                    start_date = st.date_input("Fecha inicio *", value=datetime.now())
                    start_time = st.time_input("Hora inicio *", value=datetime.now().replace(hour=9, minute=0))
                with c2:
                    location = st.text_input("Lugar (opcional)", placeholder="Ej: Aula 301")
                    end_date = st.date_input("Fecha fin", value=None)
                    end_time = st.time_input("Hora fin", value=None)

                description = st.text_area("Descripción", placeholder="Detalles...")
                st.caption("* Obligatorio")

                if st.form_submit_button("📅 Crear Evento", type="primary", use_container_width=True):
                    if not title.strip():
                        st.error("El título es obligatorio")
                    else:
                        start_dt = datetime.combine(start_date, start_time).isoformat()
                        end_dt = None
                        if end_date and end_time:
                            end_dt = datetime.combine(end_date, end_time).isoformat()
                        elif end_date:
                            end_dt = datetime.combine(end_date, start_time).isoformat()

                        with st.spinner("Creando en Google Calendar..."):
                            event_id = calendar_create_event(title.strip(), start_dt, end_dt,
                                                             location.strip() or None, description.strip())
                        if event_id:
                            fake_id = f"manual_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
                            mark_processed(
                                email_id=fake_id, thread_id="", subject=f"[Manual] {title.strip()}",
                                sender="webui", has_event=True, event_id=event_id,
                                event_title=title.strip(), event_start=start_dt, status="processed",
                            )
                            st.success(f"✅ Evento creado: {title}")
                            st.markdown(f"🔗 [Ver en Calendar](https://calendar.google.com/calendar/u/0/r/eventedit/{event_id})")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ No se pudo crear")

    with tab5:
        st.header("📋 Logs de AUTOVIEW")
        log_file = config.db_path.parent / "app.log"
        auto = st.checkbox("Auto-refresh (5s)", value=False)
        lines = st.slider("Líneas", 50, 500, 200)
        if st.button("🔄 Refrescar"):
            st.rerun()

        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
            last_lines = all_lines[-lines:]
            st.code("".join(last_lines), language="log")
            st.caption(f"Mostrando últimas {len(last_lines)} de {len(all_lines)} líneas")
        else:
            st.warning(f"No se encontró {log_file}")

        if auto:
            st.toast("🔄 Auto-refresh cada 5s")
            time.sleep(5)
            st.rerun()

    with tab6:
        st.header("▶️ Ejecutar AUTOVIEW")
        st.markdown("Ejecuta el ciclo completo manualmente.")
        dry_run = st.checkbox("Modo dry-run (no crear eventos)")

        if st.button("🚀 Ejecutar AUTOVIEW ahora", type="primary", use_container_width=True,
                     disabled=st.session_state.get("run_status") == "running"):
            st.session_state.run_status = "running"
            st.session_state.run_output = ""
            st.rerun()

        if st.session_state.get("run_status") == "running":
            with st.spinner("Ejecutando AUTOVIEW..."):
                cmd = [sys.executable, "main.py"]
                if dry_run:
                    cmd.append("--dry-run")
                code, out, err = run_cmd(cmd, timeout=180)
                output = out + "\n" + err
                st.session_state.run_output = output
                st.session_state.run_status = "done" if code == 0 else "error"
            st.rerun()

        if st.session_state.get("run_output"):
            st.subheader("📤 Output")
            st.code(st.session_state.run_output, language="log")
            if st.session_state.run_status == "done":
                st.success("✅ Completado")
                add_timeline("AUTOVIEW ejecutado desde WebUI", "AUTOVIEW", "success")
            elif st.session_state.run_status == "error":
                st.error("❌ Error")
                add_timeline(f"AUTOVIEW error: {st.session_state.run_output[:200]}", "AUTOVIEW", "error")

            if st.button("🗑️ Limpiar"):
                st.session_state.run_output = ""
                st.session_state.run_status = None
                st.rerun()


def show_email_detail(email_id: str, get_email_by_id, update_email_record,
                      delete_email_record, calendar_delete_event, ensure_auth):
    record = get_email_by_id(email_id)
    if not record:
        st.error("No encontrado")
        st.session_state.selected_email = None
        st.rerun()
        return

    if st.button("⬅ Volver"):
        st.session_state.selected_email = None
        st.rerun()

    st.subheader(f"📧 {record['subject']}")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Email ID:** `{record['email_id']}`")
        st.markdown(f"**Thread ID:** `{record['thread_id'] or '—'}`")
        st.markdown(f"**Remitente:** {record['sender']}")
    with c2:
        st.markdown(f"**Procesado:** {record['processed_at']}")
        st.markdown(f"**Estado:** `{record['status']}`")
        st.markdown(f"**Tiene evento:** {'✅' if record['has_event'] else '❌'}")

    st.divider()
    st.subheader("📅 Evento Asociado")

    if record["has_event"] and record["event_title"]:
        with st.form(key=f"edit_event_{email_id}"):
            new_title = st.text_input("Título", value=record["event_title"] or "")
            new_start = st.text_input("Fecha inicio (ISO)", value=record["event_start"] or "")
            new_status = st.selectbox("Estado", ["processed", "error", "skipped"],
                                      index=["processed", "error", "skipped"].index(record["status"]))

            c1, c2 = st.columns(2)
            with c1:
                if st.form_submit_button("💾 Guardar", type="primary", use_container_width=True):
                    update_email_record(email_id, event_title=new_title, event_start=new_start, status=new_status)
                    st.success("✅ Guardado")
                    time.sleep(0.5)
                    st.rerun()
            with c2:
                if record.get("event_id"):
                    if st.form_submit_button("🗑️ Eliminar Calendar + DB", type="secondary", use_container_width=True):
                        if ensure_auth():
                            ok = calendar_delete_event(record["event_id"])
                            delete_email_record(email_id)
                            st.success("✅ Eliminado")
                            st.session_state.selected_email = None
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("Autentícate primero")

        if record.get("event_id"):
            st.markdown(f"**Calendar ID:** `{record['event_id']}`")
            st.markdown(f'🔗 [Abrir en Calendar](https://calendar.google.com/calendar/u/0/r/eventedit/{record["event_id"]})')
    else:
        st.info("Sin evento asociado")
        if st.button("🗑️ Eliminar registro"):
            delete_email_record(email_id)
            st.session_state.selected_email = None
            st.rerun()


# ─── Página: JARVIS ─────────────────────────────────────────────────────
def page_jarvis():
    st.header("🗣️ JARVIS — Asistente de Voz")

    # Estado de conexión
    jarvis_ok = st.session_state.jarvis_connected
    status_col1, status_col2, status_col3 = st.columns(3)
    with status_col1:
        st.metric("Estado", "🟢 Conectado" if jarvis_ok else "🔴 Desconectado")
    with status_col2:
        if jarvis_ok:
            try:
                r = requests.get(f"{JARVIS_API}/status", timeout=2)
                if r.status_code == 200:
                    data = r.json()
                    st.metric("Modelo", data.get("model", "?"))
                    st.metric("Voz", "🟢 Activada" if data.get("voice_enabled") else "🔴 Desactivada")
            except Exception:
                pass

    st.divider()

    # Chat con JARVIS
    st.subheader("💬 Chat")

    # Mostrar historial
    for msg in st.session_state.jarvis_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input
    user_input = st.chat_input("Escribe a JARVIS...")
    if user_input:
        st.session_state.jarvis_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("JARVIS pensando..."):
                try:
                    r = requests.post(
                        f"{JARVIS_API}/api/chat",
                        json={"message": user_input, "speak": False},
                        timeout=30,
                    )
                    if r.status_code == 200:
                        response = r.json().get("response", "(sin respuesta)")
                    else:
                        response = f"Error HTTP {r.status_code}"
                except Exception as e:
                    response = f"❌ Error de conexión: {e}"

            st.markdown(response)
            st.session_state.jarvis_history.append({"role": "assistant", "content": response})

        add_timeline(f"Chat JARVIS: {user_input[:50]}", "JARVIS", "info")

    # Controles de voz
    st.divider()
    st.subheader("🎤 Control de Voz")
    vcol1, vcol2, vcol3 = st.columns(3)

    with vcol1:
        if st.button("🔊 Activar Voz", use_container_width=True, disabled=jarvis_ok):
            try:
                r = requests.post(f"{JARVIS_API}/voice/toggle", timeout=5)
                if r.status_code == 200 and r.json().get("enabled"):
                    st.success("Voz activada")
                    st.session_state.jarvis_connected = True
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    with vcol2:
        if st.button("🔇 Desactivar Voz", use_container_width=True, disabled=not jarvis_ok):
            try:
                r = requests.post(f"{JARVIS_API}/voice/toggle", timeout=5)
                if r.status_code == 200 and not r.json().get("enabled"):
                    st.success("Voz desactivada")
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    with vcol3:
        if st.button("🔄 Refrescar Estado", use_container_width=True):
            st.session_state.jarvis_connected = check_jarvis()
            st.rerun()

    # Configuración JARVIS
    with st.expander("⚙️ Configuración JARVIS"):
        if jarvis_ok:
            try:
                r = requests.get(f"{JARVIS_API}/api/settings", timeout=5)
                if r.status_code == 200:
                    try:
                        settings = r.json()
                        st.json(settings)
                    except Exception:
                        st.error("Error al decodificar configuración")
            except Exception:
                st.error("No se pudo obtener configuración")

        st.markdown("**Endpoints disponibles:**")
        st.code(f"""
Chat:        POST {JARVIS_API}/api/chat
Transcribe:  POST {JARVIS_API}/api/transcribe
Status:      GET  {JARVIS_API}/status
Settings:    GET/POST {JARVIS_API}/api/settings
Models:      GET  {JARVIS_API}/api/models
Voice Toggle: POST {JARVIS_API}/voice/toggle
        """)


# ─── Página: Agenda ─────────────────────────────────────────────────────
def page_agenda():
    st.header("📅 Agenda — Google Calendar + Vault")

    # Google Calendar (desde AUTOVIEW)
    try:
        from src.auth import get_credentials
        from src.calendar_writer import list_upcoming_events
        from src.config import config
    except ImportError:
        st.error("Módulos AUTOVIEW no disponibles")
        return

    @st.dialog("🔐 Autenticación Google")
    def auth_dialog():
        st.markdown("Autentícate para acceder a Google Calendar.")
        if st.button("Autenticar", type="primary", use_container_width=True):
            with st.spinner("Abriendo navegador..."):
                creds = get_credentials()
                if creds:
                    st.session_state.autoview_creds = creds
                    st.session_state.autoview_auth_ok = True
                    st.success("✅ Autenticado")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Falló")

    def ensure_auth() -> bool:
        if not st.session_state.autoview_auth_ok or not st.session_state.autoview_creds:
            auth_dialog()
            return False
        creds = st.session_state.autoview_creds
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            st.session_state.autoview_creds = creds
        return True

    # Tabs: Calendar + Vault + School
    tab1, tab2, tab3 = st.tabs(["📅 Google Calendar", "📓 Vault (Obsidian)", "📚 School API"])

    with tab1:
        if not ensure_auth():
            st.warning("Autentícate para ver Calendar")
        else:
            c1, c2 = st.columns([4, 1])
            with c1:
                st.subheader("Próximos Eventos")
            with c2:
                if st.button("🔄 Refrescar"):
                    st.rerun()

            events = list_upcoming_events(st.session_state.autoview_creds, 30)
            if events:
                for ev in events:
                    start = ev.get("start", {})
                    start_str = start.get("dateTime", start.get("date", "?"))
                    try:
                        dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                        start_str = dt.strftime("%d/%m/%Y %H:%M")
                    except Exception:
                        pass
                    with st.expander(f"**{ev.get('summary', 'Sin título')}** — {start_str}"):
                        st.markdown(f"**ID:** `{ev.get('id', '?')}`")
                        st.markdown(f"**Link:** [Abrir]({ev.get('htmlLink', '#')})")
                        if ev.get("description"):
                            st.markdown(f"**Desc:** {ev['description'][:500]}")
            else:
                st.info("Sin eventos próximos")

    with tab2:
        st.subheader("📓 Notas del Vault (Obsidian)")
        vault_notes = VAULT_PATH / "Notas" if (VAULT_PATH / "Notas").exists() else VAULT_PATH

        # Buscar archivos .md recientes — con timeout para evitar colgarse
        try:
            md_files = []
            for f in vault_notes.rglob("*.md"):
                md_files.append(f)
                if len(md_files) >= 100:
                    break
        except Exception:
            md_files = []

        if md_files:
            md_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

            for md_file in md_files[:20]:
                try:
                    content = md_file.read_text(encoding="utf-8")
                    title = md_file.stem
                    if content.startswith("---"):
                        try:
                            fm_end = content.index("---", 3)
                            fm = yaml.safe_load(content[3:fm_end])
                            title = fm.get("title", title)
                        except Exception:
                            pass

                    with st.expander(f"📄 {title} ({md_file.relative_to(VAULT_PATH)})"):
                        st.code(content[:1000], language="markdown")
                        if len(content) > 1000:
                            st.caption(f"... ({len(content)} chars total)")
                except Exception:
                    pass
        else:
            st.info("No se encontraron notas .md en el vault")

    with tab3:
        st.subheader("📚 School API — Tareas y Exámenes")
        try:
            # Tareas
            r = requests.get(f"{SCHOOL_API}/tareas/", timeout=5)
            if r.status_code == 200:
                tareas = r.json()
                if tareas:
                    st.markdown("### 📝 Tareas")
                    df = pd.DataFrame(tareas)
                    if "completada" in df.columns:
                        df["completada"] = df["completada"].apply(lambda x: "✅" if x else "⏳")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("Sin tareas")

            # Exámenes
            r = requests.get(f"{SCHOOL_API}/examenes/", timeout=5)
            if r.status_code == 200:
                examenes = r.json()
                if examenes:
                    st.markdown("### 📝 Exámenes")
                    df = pd.DataFrame(examenes)
                    st.dataframe(df, use_container_width=True, hide_index=True)

            # IA
            st.divider()
            st.markdown("### 🤖 IA")
            icol1, icol2 = st.columns(2)
            with icol1:
                if st.button("📋 Resumen Semana", use_container_width=True):
                    with st.spinner("Generando..."):
                        r = requests.get(f"{SCHOOL_API}/ai/resumen-semana", timeout=30)
                        if r.status_code == 200:
                            st.markdown(r.json().get("resumen", "Sin respuesta"))
                        else:
                            st.error(f"Error: {r.text}")
            with icol2:
                if st.button("🎯 Prioridades Hoy", use_container_width=True):
                    with st.spinner("Generando..."):
                        r = requests.get(f"{SCHOOL_API}/ai/prioridades", timeout=30)
                        if r.status_code == 200:
                            st.markdown(r.json().get("recomendacion", "Sin respuesta"))
                        else:
                            st.error(f"Error: {r.text}")

        except Exception as e:
            st.error(f"Error conectando a School API: {e}")


# ─── Página: Sistema ────────────────────────────────────────────────────
def page_sistema():
    st.header("📊 Sistema — Monitor de Recursos")

    # Métricas en tiempo real
    col1, col2, col3, col4 = st.columns(4)

    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()

    with col1:
        st.metric("🖥️ CPU", f"{cpu:.1f}%")
        st.progress(cpu / 100)
    with col2:
        st.metric("🧠 RAM", f"{ram.percent:.1f}%", f"{ram.used / 1e9:.1f} / {ram.total / 1e9:.1f} GB")
        st.progress(ram.percent / 100)
    with col3:
        st.metric("💾 Disco", f"{disk.percent:.1f}%", f"{disk.used / 1e9:.1f} / {disk.total / 1e9:.1f} GB")
        st.progress(disk.percent / 100)
    with col4:
        st.metric("🌐 Red", f"↑ {net.bytes_sent / 1e6:.1f} MB", f"↓ {net.bytes_recv / 1e6:.1f} MB")

    st.divider()

    # Procesos top
    st.subheader("🔥 Top Procesos (CPU)")
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            procs.append(p.info)
        except Exception:
            pass
    procs.sort(key=lambda x: x["cpu_percent"] or 0, reverse=True)
    df_procs = pd.DataFrame(procs[:15])
    if not df_procs.empty:
        st.dataframe(
            df_procs.rename(columns={"pid": "PID", "name": "Proceso", "cpu_percent": "CPU %", "memory_percent": "RAM %"}),
            use_container_width=True, hide_index=True,
        )

    st.divider()

    # Servicios systemd
    st.subheader("⚙️ Servicios Systemd (clave)")
    key_services = [
        "ollama", "docker", "nginx", "postgresql", "redis",
        "autoview.timer", "jarvis", "school-api",
    ]
    svc_data = []
    for svc in key_services:
        code, out, err = run_cmd(["systemctl", "is-active", svc], timeout=5)
        status = out.strip() if code == 0 else "not-found"
        svc_data.append({"Servicio": svc, "Estado": status})

    df_svc = pd.DataFrame(svc_data)
    def style_status(v):
        colors = {"active": "green", "inactive": "orange", "failed": "red", "not-found": "gray"}
        return f"color: {colors.get(v, 'gray')}; font-weight: bold"
    st.dataframe(df_svc.style.map(style_status, subset=["Estado"]), use_container_width=True, hide_index=True)

    st.divider()

    # GPU (si hay nvidia-smi)
    st.subheader("🎮 GPU (NVIDIA)")
    code, out, err = run_cmd(["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                               "--format=csv,noheader,nounits"], timeout=5)
    if code == 0 and out.strip():
        lines = out.strip().split("\n")
        gpu_data = []
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                gpu_data.append({
                    "GPU": parts[0],
                    "VRAM Usada (MB)": int(parts[1]),
                    "VRAM Total (MB)": int(parts[2]),
                    "Uso %": int(parts[3]),
                    "Temp (°C)": int(parts[4]),
                })
        if gpu_data:
            df_gpu = pd.DataFrame(gpu_data)
            st.dataframe(df_gpu, use_container_width=True, hide_index=True)
        else:
            st.info("Sin GPUs detectadas")
    else:
        st.info("nvidia-smi no disponible o sin GPU NVIDIA")


# ─── Página: Acciones ───────────────────────────────────────────────────
def page_acciones():
    st.header("⚙️ Acciones Rápidas + Timeline")

    st.subheader("⚡ Acciones Rápidas")
    acol1, acol2, acol3, acol4 = st.columns(4)

    with acol1:
        st.markdown("**🤖 JARVIS**")
        if st.button("🗣️ Hablar con JARVIS (WebUI)", use_container_width=True):
            st.markdown(f"[Abrir JARVIS WebUI]({JARVIS_API})")
        if st.button("🔄 Reiniciar JARVIS", use_container_width=True):
            code, out, err = run_cmd(["systemctl", "restart", "jarvis"], timeout=10)
            if code == 0:
                st.success("JARVIS reiniciado")
                add_timeline("JARVIS reiniciado via systemctl", "JARVIS", "success")
            else:
                st.error(f"Error: {err}")
                add_timeline(f"Fallo reinicio JARVIS: {err}", "JARVIS", "error")

    with acol2:
        st.markdown("**📬 AUTOVIEW**")
        if st.button("🚀 Ejecutar AUTOVIEW", use_container_width=True):
            code, out, err = run_cmd([sys.executable, "main.py"], timeout=180)
            if code == 0:
                st.success("✅ Completado")
                add_timeline("AUTOVIEW ejecutado", "AUTOVIEW", "success")
            else:
                st.error(f"❌ {err}")
                add_timeline(f"AUTOVIEW error: {err}", "AUTOVIEW", "error")
        if st.button("📊 Ver Dashboard AUTOVIEW", use_container_width=True):
            st.markdown("[Abrir Dashboard](http://localhost:8501)")

    with acol3:
        st.markdown("**📚 School**")
        if st.button("🔄 Sync Vault → DB", use_container_width=True):
            try:
                r = requests.post(f"{SCHOOL_API}/sync/importar", timeout=30)
                if r.status_code == 200:
                    st.success(f"✅ {r.json()}")
                    add_timeline("Sync Vault→DB", "SCHOOL", "success")
                else:
                    st.error(r.text)
            except Exception as e:
                st.error(str(e))
        if st.button("📤 Exportar DB → Vault", use_container_width=True):
            try:
                r = requests.post(f"{SCHOOL_API}/sync/exportar", timeout=30)
                if r.status_code == 200:
                    st.success(f"✅ {r.json()}")
                    add_timeline("Export DB→Vault", "SCHOOL", "success")
                else:
                    st.error(r.text)
            except Exception as e:
                st.error(str(e))

    with acol4:
        st.markdown("**🖥️ Sistema**")
        if st.button("🔄 Reiniciar Ollama", use_container_width=True):
            code, out, err = run_cmd(["systemctl", "restart", "ollama"], timeout=15)
            if code == 0:
                st.success("Ollama reiniciado")
                add_timeline("Ollama reiniciado", "SISTEMA", "success")
            else:
                st.error(err)
        if st.button("🧹 Limpiar Docker", use_container_width=True):
            code, out, err = run_cmd(["docker", "system", "prune", "-f"], timeout=60)
            if code == 0:
                st.success("Docker limpiado")
                add_timeline("Docker system prune", "SISTEMA", "info")
            else:
                st.error(err)

    st.divider()

    # Timeline cross-proyecto
    st.subheader("📜 Timeline Cross-Proyecto")
    tcol1, tcol2 = st.columns([3, 1])
    with tcol1:
        filter_source = st.selectbox("Filtrar por origen", ["Todos", "AUTOVIEW", "JARVIS", "SCHOOL", "SISTEMA"])
    with tcol2:
        if st.button("🗑️ Limpiar Timeline"):
            st.session_state.timeline_events = []
            st.rerun()

    events = st.session_state.timeline_events
    if filter_source != "Todos":
        events = [e for e in events if e["source"] == filter_source]

    if events:
        df = pd.DataFrame(events)
        # Colorear por nivel
        def style_level(row):
            colors = {"info": "blue", "success": "green", "error": "red", "warning": "orange"}
            c = colors.get(row["level"], "black")
            return [f"color: {c}"] * len(row)

        st.dataframe(
            df[["time", "source", "event", "level"]].rename(columns={
                "time": "Hora", "source": "Origen", "event": "Evento", "level": "Nivel"
            }).style.apply(style_level, axis=1),
            use_container_width=True, hide_index=True, height=400,
        )
    else:
        st.info("Timeline vacío. Ejecuta acciones para poblarlo.")


# ─── Main ───────────────────────────────────────────────────────────────
def main():
    render_sidebar()

    pages = {
        "🏠 Home": page_home,
        "📬 AUTOVIEW": page_autoview,
        "🗣️ JARVIS": page_jarvis,
        "📅 Agenda": page_agenda,
        "📊 Sistema": page_sistema,
        "⚙️ Acciones": page_acciones,
    }

    page_func = pages.get(st.session_state.page, page_home)
    page_func()


if __name__ == "__main__":
    main()