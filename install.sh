#!/usr/bin/env bash
# install.sh — Setup inicial de AUTOVIEW
# Uso: bash install.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "=== AUTOVIEW — Instalación ==="
echo ""

# 1. Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 no está instalado. Instálalo primero."
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python detectado: $PY_VERSION"

# 2. Crear venv
if [ ! -d ".venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv .venv
fi

# 3. Activar e instalar
echo "Instalando dependencias..."
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo ""
echo "Dependencias instaladas."

# 4. Crear .env si no existe
if [ ! -f "config/.env" ]; then
    cp config/.env.example config/.env
    echo "Creado config/.env desde template — EDITA los valores antes de ejecutar."
else
    echo "config/.env ya existe."
fi

# 5. Verificar Ollama (si está configurado)
if command -v ollama &> /dev/null; then
    echo ""
    echo "Ollama detectado. Modelos disponibles:"
    ollama list 2>/dev/null || echo "  (no se pudieron listar modelos)"
    echo ""
    echo "Si no tienes el modelo configurado, descárgalo:"
    echo "  ollama pull llama3.1:8b"
else
    echo ""
    echo "ADVERTENCIA: Ollama no está instalado."
    echo "  Instálalo desde https://ollama.com"
    echo "  O cambia LLM_PROVIDER=openai en config/.env"
fi

# 6. Verificar credentials.json
if [ ! -f "config/credentials.json" ]; then
echo ""
echo "ADVERTENCIA: Falta config/credentials.json"
echo "  Sigue la guía en docs/SETUP_GOOGLE.md (u online: console.cloud.google.com)"
fi

echo ""
echo "=== Instalación completa ==="
echo ""
echo "Siguientes pasos:"
echo "  1. Editar config/.env con tus valores"
echo "  2. Colocar credentials.json en config/ (ver docs/SETUP_GOOGLE.md)"
echo "  3. Probar:        python main.py --dry-run"
echo "  4. Ejecutar:      python main.py"
echo "  5. Automatizar:   ver README.md (sección cron)"
echo ""
echo "Para activar el venv manualmente:  source .venv/bin/activate"
