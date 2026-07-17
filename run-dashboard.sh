#!/bin/bash
# Lanzador del Dashboard AUTOVIEW
# Abre Streamlit y el navegador automáticamente

cd /home/aaronsoto/proyectos/autoview
echo "🚀 Iniciando AUTOVIEW Dashboard..."
echo "📅 Abriendo http://localhost:8501"
xdg-open http://localhost:8501 2>/dev/null &
exec .venv/bin/streamlit run dashboard.py --server.port 8501
