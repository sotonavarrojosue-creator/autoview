# Setup Google Cloud — AUTOVIEW

Esta guía la haces **una sola vez**. Tarda ~10 minutos.

## 1. Crear proyecto en Google Cloud

1. Ve a https://console.cloud.google.com/
2. Click **"Seleccionar un proyecto"** → **"Proyecto nuevo"**
3. Nombre: `AUTOVIEW` (o el que quieras)
4. Click **Crear**

## 2. Habilitar APIs

1. En el menú izquierdo: **APIs y servicios → Biblioteca**
2. Busca y habilita:
   - **Gmail API** → click **Habilitar**
   - **Google Calendar API** → click **Habilitar**

## 3. Configurar pantalla de consentimiento OAuth

1. **APIs y servicios → Pantalla de consentimiento OAuth**
2. Tipo de usuario: **Externo** (aunque seas solo tú)
3. Completa:
   - App name: `AUTOVIEW`
   - Email de soporte: tu correo
   - Developer contact: tu correo
4. Click **Guardar y continuar**
5. **Scopes**: click **Add or Remove Scopes**
   - Busca `gmail.readonly` → marcar
   - Busca `calendar.events` → marcar
   - Click **Guardar y continuar**
6. **Test users**: añade tu propio correo de Gmail
7. Click **Guardar y continuar**

## 4. Crear credenciales OAuth2

1. **APIs y servicios → Credenciales**
2. Click **"+ CREAR CREDENCIALES" → "ID de cliente OAuth"**
3. Tipo de app: **Aplicación de escritorio** (Desktop app)
4. Nombre: `AUTOVIEW Client`
5. Click **Crear**
6. Click **Descargar JSON** → guarda el archivo

## 5. Colocar el archivo en el proyecto

```bash
# Renombra el archivo descargado y muévelo a config/
mv ~/Downloads/client_secret_*.json ~/proyectos/autoview/config/credentials.json
```

## 6. Verificar

```bash
cd ~/proyectos/autoview
python -c "from src.config import config; print(config.validate())"
# Debe imprimir: []
```

## Notas

- La **primera vez** que corras `python main.py` se abrirá el navegador pidiendo permiso.
- Se guarda el token en `data/token.json` para no volver a pedirlo.
- Si cambias de cuenta o scopes, borra `data/token.json` y se vuelve a pedir.
- El proyecto está en modo **"Testing"** — solo funciona con los correos que añadiste como test users. Suficiente para uso personal.
