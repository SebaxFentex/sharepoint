# AGENTS.md — ms365

Guía para agentes (y humanos) que trabajan en este repo. Las reglas con
"porqué" vienen de bugs reales; no relajarlas sin evidencia nueva.

## 1. Proyecto en 30 segundos

Automatización de SharePoint Online con Playwright + Chromium usando credenciales
de usuario con MFA. No hay app en Entra (restricción corporativa: sin
client_id propio; la vía REST con `office365-rest-python-client` se probó y el
tenant la bloquea) — por eso todo pasa por el navegador.

Stack: Python 3.14, `uv`, layout `src/`, build `uv_build` (`uv build`).
Instalar: `uv sync` + `uv run playwright install chromium` (una vez; se usa el
Chromium bundled, sin `channel`).

```
src/ms365/
  __init__.py        # solo NullHandler (ver §4)
  _logging.py        # setup_logging() + prune_logs() — sin efectos al importar
  sharepoint/
    __init__.py      # SharepointClient + excepciones (NO re-exporta login)
    _base.py         # profile_dir() y browser_window_kwargs() — rutas fijas
    _exceptions.py   # NotAuthenticatedException, FolderNotFoundException
    auth.py          # login() interactivo + main() para `python -m`
    client.py        # SharepointClient (operaciones con sesión válida)
scripts/
  login.bat          # único .bat: `uv run python -m ms365.sharepoint.auth`
tests/
  test_*.py          # e2e contra la carpeta de MS365_TEST_FOLDER_URL (exigen MFA humano; sin defaults, fallan con mensaje)
  files/upload/      # fixtures locales (no usar rutas personales)
  files/download/    # salida de descargas: se limpia antes de cada test, ignorada por git
```

## 2. Arquitectura y API

- `SharepointClient(user_email, home_url, headless=True, slow_mo=0)`:
  context manager con sesión persistente de Chromium. `user_email` y
  `home_url` son requeridos, sin defaults. Métodos públicos: `upload_files`,
  `upload_folders`, `download_folder`, `download_single_file`.
- `upload_folders` omite carpetas locales vacías. Para las no vacías, elimina
  primero la carpeta homónima de SharePoint con su contenido; conserva archivos
  homónimos.
- `auth.login(home_url=...) -> Path`: abre el perfil en headed, espera Enter,
  cierra. Sirve igual para primer login y refresco (son la misma operación).
- Orden de métodos en la clase: dunder → públicos → privados.
- UI del tenant en español: selectores `Cargar/Descargar/Reemplazar`.

## 3. Reglas inviolables

1. **Perfil siempre fijo**: `%LOCALAPPDATA%\programas_python\ms365\perfil_navegador_playwright`. Sin params,
   sin env vars, sin perfiles del navegador (ver `_base.profile_dir()`).
2. **`input()` solo existe en `auth.py`**. Ninguna ruta programada abre
   ventanas ni espera humanos: las corridas van al scheduler y deben fallar
   rápido (ver §5).
3. **La librería emite, el entrypoint configura**: `getLogger(__name__)` +
   `NullHandler` en el paquete; `setup_logging()` solo se llama desde
   `tests/*` y `auth.main()`. Jamás configurar logging en `__init__` ni en
   constructores.
4. **`scripts/` solo `.bat`** que invocan `uv run python -m ...`. Nada de
   `python -c` con quoting.
5. **Prohibido `click(force=True)`**: salta accionabilidad y produce clics
   fantasma (causó la intermitencia del upload). Si un clic falla, que falle
   con diagnóstico.
6. **Prohibido `timeout=0`**: espera infinita (causó el pegue eterno del
   upload). Todo wait lleva deadline finito.
7. **Reintentos con estado fresco** (recarga de página), nunca sobre UI a
   medio abrir. Sin fallback a input oculto (se probó: no sirve).
8. **Un log por paso**: INFO auditable / DEBUG diagnóstico / ERROR
   intervención. URLs con UniqueId solo en DEBUG. Sin `print()` en librería
   ni tests (el prompt al operador en `auth.login` es la única excepción).
9. **Sin re-exports en `__init__`** de módulos que se corren con `-m`
   (provoca el RuntimeWarning de runpy por doble instancia).
10. **Tamaño de ventana centralizado** en `browser_window_kwargs()`: headed
    `no_viewport=True` (+ `--window-size` inicial), headless viewport
    1920×1080. `--start-maximized` no sirve (no toca el viewport).
11. **Nada especulativo**: sin abstracciones de un solo uso, sin params de
    "por si acaso". Lo muerto se borra (queda en git si se necesita).
12. **`.env` es del consumidor, no de la librería**: `ms365` jamás carga
    dotenv ni lee `MS365_*` salvo `setup_logging()` (nivel, prefijo y
    retención de logs). Solo los entrypoints propios (`tests/*`,
    `auth.main()`) leen env; las requeridas fallan con mensaje si faltan
    (sin defaults reales). `.env` local está en
    `.gitignore`, se versiona `.env.example` con placeholders.

## 4. Logging

- Archivo + consola vía `setup_logging()` (una línea al inicio de cada
  entrypoint). Nivel por env `MS365_LOG_LEVEL` (default INFO).
- Archivos en `%LOCALAPPDATA%\programas_python\ms365\logs` (utf-8), con prefijo
  `MS365_LOG_FILE_PREFIX` (default `ms365-`); purga a los `MS365_MAX_LOG_FILES`
  más recientes (default **30**).
- Cada corrida genera su propio log: ante un fallo, leer **el de mayor
  timestamp**, nunca uno viejo.

## 5. Scheduler y códigos de salida

- `0` OK · `2` carpeta inexistente · `3` autenticación (corre
  `scripts/login.bat` en sesión interactiva y reintenta).
- La tarea corre como el **mismo usuario Windows** dueño del perfil, en
  `headless=True`. Sesión muerta = exit 3, sin reintento automático (con MFA
  no hay refresh desatendido posible).

## 6. Verificación antes de dar por hecho

1. `py_compile` + import smoke (con `RuntimeWarning` como error para `-m`).
2. Lógica nueva con dobles falsos **sin browser** (reintentos, purga,
   resolución de botones/kwargs). El e2e real exige MFA humano.
3. `uv build` OK.
4. Greps de guardia: cero `force=True`, `input(` solo en `auth.py`,
   cero `timeout=0`, cero `set_input_files` en el flujo de upload.
