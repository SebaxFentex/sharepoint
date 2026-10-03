# ms365

Libreria Python para automatizar operaciones de SharePoint con Playwright (Chromium).

## Estado actual

- Cliente unificado: SharepointClient
- Soporte de subida de archivos y carpetas
- Descarga de carpetas (zip + extraccion)
- Descarga de archivo compartido mediante download.aspx
- Manejo de errores por excepcion (sin retornos bool para download_folder)

## Requisitos

- Python 3.14+
- Chromium de Playwright (`uv run playwright install chromium`, una vez)
- Sesion de Microsoft 365 iniciada en el perfil dedicado (ver Perfil y login)

## Instalacion

Con uv (crea `.venv` en 3.14 e instala editable):

```bash
uv sync
```

## Perfil y login

No usa tus perfiles del navegador. Cada ejecucion usa un perfil dedicado,
siempre en `%LOCALAPPDATA%\programas_python\ms365\perfil_navegador_playwright`,
sin excepciones. Se usa el Chromium de Playwright (`playwright install chromium`).

Primera vez o sesion vencida: doble clic a `scripts/login.bat`, inicia sesion
con MFA en el navegador y pulsa Enter. Sirve igual para primer login y refresco.

## Estructura relevante

```text
src/ms365/
  _logging.py        # setup_logging() para entrypoints (la libreria solo emite)
  sharepoint/
    __init__.py
    _base.py         # rutas fijas: perfil y logs en %LOCALAPPDATA%/programas_python/ms365
    _exceptions.py
    auth.py          # login() interactivo (`python -m ms365.sharepoint.auth`)
    client.py
scripts/
  login.bat          # abre el perfil para login/refresco manual
tests/
  test_upload_files.py       # sube *.txt de files/upload/
  test_upload_folders.py     # sube carpetas no vacias; reemplaza carpeta homonima
  test_download_folders.py   # baja folder_1/2/3 a files/download/ (limpia antes)
  test_download_single_file.py  # baja file_1.txt a files/download/ (limpia y verifica)
  files/upload/    # fixtures locales (file_*.txt, folder_1/2/3; folder_3 vacia)
  files/download/  # salida de descargas (ignorada por git)
```

Carpeta de pruebas en SharePoint: la definida en `MS365_TEST_FOLDER_URL`
(`.env` local, no versionado).

## Tests

```bash
uv run python tests/test_upload_files.py
uv run python tests/test_upload_folders.py
uv run python tests/test_download_folders.py
uv run python tests/test_download_single_file.py
```

Con `.env` local (ver Configuración):

```bash
uv run --env-file .env -- python tests/test_upload_files.py
```

Códigos de salida: `0` OK · `2` carpeta inexistente · `3` autenticación
(corre `scripts/login.bat` y reintenta). Diagnóstico con
`MS365_LOG_LEVEL=DEBUG`. Requieren MFA humano; el scheduler corre en
`headless=True` como el mismo usuario Windows dueño del perfil.
Los tests exigen `.env` local con `MS365_USER_EMAIL`, `MS365_HOME_URL`,
`MS365_TEST_FOLDER_URL` (y `MS365_TEST_SHARED_FILE_URL` para el de archivo);
sin ellos salen con mensaje, sin defaults.

## Configuración (.env local)

`ms365` es una librería: no busca ni carga ningún `.env`, solo recibe
parámetros explícitos (`user_email`, `headless`, `home_url`, ...). El `.env`
es del proyecto que la usa. En este repo hay uno local solo para los
entrypoints propios (tests, login):

```bash
copy .env.example .env
uv run --env-file .env -- python tests/test_upload_files.py
```

Variables requeridas para los tests (fallan con mensaje si faltan):
`MS365_USER_EMAIL`, `MS365_HOME_URL`, `MS365_TEST_FOLDER_URL`,
`MS365_TEST_SHARED_FILE_URL` (solo el test de archivo). Opcionales:
`MS365_HEADLESS` (`true`/`false`), `MS365_LOG_LEVEL`, `MS365_LOG_FILE_PREFIX`,
`MS365_MAX_LOG_FILES` (estas tres últimas solo ajustan los logs de los
entrypoints de este repo). `scripts/login.bat` carga `.env` solo si existe.
`.env` está en `.gitignore`; se versiona únicamente `.env.example` con placeholders.

## Logging

Cada corrida genera un log en `%LOCALAPPDATA%\programas_python\ms365\logs` y duplica
a consola. El nombre por defecto es `ms365-%Y%m%d-%H%M%S.log` y conserva los 30
logs más recientes; prefijo y retención se ajustan con `MS365_LOG_FILE_PREFIX` y
`MS365_MAX_LOG_FILES`. Nivel por `MS365_LOG_LEVEL` (default INFO). Ante un fallo,
leer el log de mayor timestamp.

## API publica (sharepoint)

Se recomienda importar desde ms365.sharepoint:

```python
from ms365.sharepoint import (
    SharepointClient,
    NotAuthenticatedException,
    FolderNotFoundException,
)
from ms365.sharepoint.auth import login  # login interactivo (scripts/login.bat)
```

## Excepciones

- NotAuthenticatedException: sesion no autenticada o contexto no disponible
- FolderNotFoundException: carpeta SharePoint inexistente (404)

## Uso rapido

### 1) Subir archivos

```python
from ms365.sharepoint import SharepointClient

with SharepointClient(user_email="usuario@empresa.com", home_url="https://empresa.sharepoint.com/.../Home.aspx") as client:
    client.upload_files(
        {
            "https://empresa.sharepoint.com/.../Reportes": [
                "C:/archivos/enero.xlsx",
                "C:/archivos/febrero.xlsx",
            ]
        }
    )
```

### 2) Subir carpetas

Las carpetas locales vacias se omiten. Si ya existe una carpeta homonima en
SharePoint, se elimina junto con su contenido antes de subir la nueva. Un
archivo homonimo se conserva.

```python
from ms365.sharepoint import SharepointClient

with SharepointClient(user_email="usuario@empresa.com", home_url="https://empresa.sharepoint.com/.../Home.aspx") as client:
    client.upload_folders(
        {
            "https://empresa.sharepoint.com/.../Respaldos": [
                "C:/carpetas/cierre_2025",
                "C:/carpetas/cierre_2026",
            ]
        }
    )
```

### 3) Descargar carpeta

download_folder no retorna valor. Si termina sin excepcion, la descarga fue exitosa.

```python
from ms365.sharepoint import (
    SharepointClient,
    FolderNotFoundException,
    NotAuthenticatedException,
)

try:
    with SharepointClient(user_email="usuario@empresa.com", home_url="https://empresa.sharepoint.com/.../Home.aspx") as client:
        client.download_folder(
            "https://empresa.sharepoint.com/.../Carpeta",
            "C:/descargas/carpeta",
        )
        print("Descarga OK")
except FolderNotFoundException:
    print("La carpeta no existe en SharePoint")
except NotAuthenticatedException:
    print("Sesion vencida, inicia sesion y reintenta")
```

### 4) Descargar archivo compartido

```python
from ms365.sharepoint import SharepointClient

with SharepointClient(user_email="usuario@empresa.com", home_url="https://empresa.sharepoint.com/.../Home.aspx") as client:
    client.download_single_file(
        "https://tenant.sharepoint.com/:x:/r/sites/SITIO/.../archivo.xlsx?d=w...",
        "C:/descargas/archivo.xlsx",
    )
```

### 5) Descargar carpeta y archivo

```python
from ms365.sharepoint import SharepointClient

with SharepointClient(user_email="usuario@empresa.com", home_url="https://empresa.sharepoint.com/.../Home.aspx") as client:
    client.download_folder(
        "https://empresa.sharepoint.com/.../Carpeta1",
        "C:/descargas/carpeta1",
    )
    client.download_single_file(
        "https://tenant.sharepoint.com/:x:/r/sites/SITIO/.../archivo.xlsx?d=w...",
        "C:/descargas/archivo.xlsx",
    )
```

## Parametros de SharepointClient

- user_email (str): correo del usuario para validaciones UI
- headless (bool): ejecutar sin UI
- slow_mo (int): retardo en ms entre acciones de Playwright (default 0, solo debug)
- home_url (str, requerido, sin default): URL para validar sesion al arrancar

## Notas operativas

- Usa contexto persistente de Chromium (launch_persistent_context) con perfil dedicado
- El perfil debe tener sesion iniciada (primera vez en headed vía `scripts/login.bat`)
- Ventana: headed sin viewport fijo (el contenido sigue a la ventana), headless 1920×1080
- Para descargar carpeta, SharePoint entrega un zip y luego se extrae
- Para archivo compartido, se construye URL directa download.aspx a partir del parametro d
- Build con uv_build (`uv build`); layout `src/`
- Reglas de contribución para agentes: ver `AGENTS.md`

## Licencia

MIT
