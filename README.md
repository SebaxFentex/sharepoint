# sharepoint

Libreria Python (paquete `uv_build`, layout `src/`) para operar SharePoint
Online con Playwright + Chromium bundled. Autenticacion con usuario + MFA
sobre perfil dedicado persistente (sin app en Entra por restriccion
corporativa; la via REST esta bloqueada por el tenant).

## Uso en un proyecto de trabajo

### 1. Declarar la dependencia

```toml
[project]
dependencies = ["sharepoint"]

[tool.uv.sources]
sharepoint = { path = "../../../../Proyectos/1. PROPIOS/1.5 - Librerias/sharepoint", editable = true }
```

(Ajustar los `../` a la profundidad real del `python_<nombre>`; luego
`uv lock && uv sync`. Con `editable` el proyecto usa el codigo de la
libreria en su carpeta real: los cambios se reflejan sin reinstalar.)

### 2. Requisitos del proyecto consumidor

- Python 3.14+.
- Chromium de Playwright instalado en su propio `.venv` (una vez por
  proyecto): `uv run playwright install chromium`.
- Sesion iniciada en el perfil dedicado (ver Perfil y login; se hace una
  vez por maquina con el `login.bat` de la libreria).

### 3. Ejemplo minimo

```python
from sharepoint import ClienteSharepoint

with ClienteSharepoint(correo_usuario="usuario@empresa.com",
                       url_inicio="https://empresa.sharepoint.com/.../Home.aspx") as cliente:
    cliente.subir_archivos({"https://empresa.sharepoint.com/.../Reportes": ["C:/archivos/enero.xlsx"]})
```

### 4. API publica

```python
from sharepoint import (
    ClienteSharepoint,
    ExcepcionArchivoNoEncontrado,
    ExcepcionCarpetaNoEncontrada,
    ExcepcionNoAutenticado,
)
from sharepoint.cliente import login_manual  # login interactivo standalone
# (o doble clic a ejecutables/login.bat, que corre `python -m sharepoint`)
```

`ClienteSharepoint(correo_usuario, url_inicio, mostrar_navegador=False, pausa_ms=0, permitir_login_interactivo=False)`:

- `subir_archivos(archivos_por_carpeta)` — sube archivos a una o varias
  carpetas de SharePoint.
- `subir_carpetas(carpetas_por_carpeta)` — sube carpetas (omite las vacias;
  reemplaza la carpeta homonima, conserva archivos homonimos).
- `descargar_carpeta(url_carpeta, carpeta_destino)` — descarga la carpeta
  como zip y la extrae.
- `descargar_archivo_compartido(url_archivo_compartido, ruta_destino)` —
  descarga un archivo desde su vinculo compartido; lanza `ValueError` si el
  vinculo es invalido y `ExcepcionArchivoNoEncontrado` si el archivo no
  existe.

Errores por excepcion: `ExcepcionCarpetaNoEncontrada` (carpeta inexistente,
codigo 2), `ExcepcionArchivoNoEncontrado` (archivo compartido inexistente,
codigo 4), `ExcepcionNoAutenticado` (sesion vencida, codigo 3: corre
`ejecutables/login.bat` en sesion interactiva y reintenta); `ValueError` si
el vinculo compartido no permite construir la URL. Codigos de los
entrypoints: `0` OK · `2` carpeta inexistente · `3` autenticacion · `4`
archivo no encontrado.

### 5. Perfil y login

Perfil dedicado en `%LOCALAPPDATA%\perfil_playwright_sharepoint` por
defecto (se cambia con `SHAREPOINT_CARPETA_PERFIL`). Primera vez o sesion
vencida: doble clic a `ejecutables/login.bat` **de la libreria**, inicia
sesion con MFA y pulsa Enter (sirve para primer login y refresco).

En produccion cada proyecto necesita su propio `ejecutables/login.bat`
con la URL como argumento (asi no necesita ninguna variable):

```bat
@echo off
cd /d "%~dp0..\python_<nombre>"
uv run python -m sharepoint https://empresa.sharepoint.com/.../Home.aspx
```

(Alternativa: `SHAREPOINT_URL_INICIO` en su `.env` y
`uv run --env-file .env python -m sharepoint`.)

**Si la sesion vence en produccion:** el cliente lanza
`ExcepcionNoAutenticado` (con `codigo_salida = 3`) al entrar al `with`. El
proyecto debe capturarla, salir con ese codigo y alertar al operador, que
corre el `login.bat` del proyecto, hace el MFA y reejecuta. No hay
reintento automatico (el MFA no se puede automatizar), salvo opt-in
explicito con `permitir_login_interactivo=True` y ventana visible: en ese
caso abre el login en la misma sesion y reintenta una vez.

### 6. Variables de entorno

La libreria no carga ningun `.env`: recibe parametros explicitos. El
proyecto consumidor lee su propio `.env` y pasa los valores al crear el
cliente. Ninguna variable `SHAREPOINT_*` es obligatoria para importar y
usar la libreria; solo configuran los entrypoints de desarrollo (ver
abajo).

## Desarrollo de la libreria

### Instalacion

```bash
uv sync
uv run playwright install chromium   # solo la primera vez
```

### Estructura relevante

```text
src/sharepoint/
  __init__.py        # NullHandler + ClienteSharepoint + excepciones (NO re-exporta iniciar_sesion)
  _log.py            # configurar_log() para entrypoints (la libreria solo emite)
  _env.py            # rutas fijas del perfil en %LOCALAPPDATA%/perfil_playwright_sharepoint
  _excepciones.py    # ExcepcionNoAutenticado, ExcepcionCarpetaNoEncontrada
  cliente.py         # ClienteSharepoint + login_manual (login en propio contexto)
  __main__.py        # renovar_autenticacion() para `python -m sharepoint` (login manual)
  _subida.py         # subir_archivos / subir_carpetas (internas, reciben pagina)
  _descarga.py       # descargar_carpeta / descargar_archivo_compartido (internas)
ejecutables/
  login.bat          # abre el perfil para login/refresco manual
  abrir_vscode.bat   # abre la raiz de la libreria en VS Code
tests/
  test_subir_archivos.py     # sube *.txt de archivos/subida/
  test_subir_carpetas.py     # sube carpetas no vacias; reemplaza carpeta homonima
  test_descargar_carpetas.py # baja carpeta_1/2/3 a archivos/descarga/ (limpia antes)
  test_descargar_archivo.py  # baja archivo_1.txt a archivos/descarga/ (limpia y verifica)
  archivos/subida/      # fixtures locales (archivo_*.txt, carpeta_1/2/3; carpeta_3 vacia)
  archivos/descarga/    # salida de descargas (ignorada por git)
logs/                   # la crea configurar_log al correr tests o login (ignorada por git)
```

### Tests (e2e, exigen MFA humano)

```bash
uv run --env-file .env python tests/test_subir_archivos.py
uv run --env-file .env python tests/test_subir_carpetas.py
uv run --env-file .env python tests/test_descargar_carpetas.py
uv run --env-file .env python tests/test_descargar_archivo.py
```

Requieren `SHAREPOINT_CORREO_USUARIO`, `SHAREPOINT_URL_INICIO`,
`SHAREPOINT_URL_CARPETA_PRUEBAS` (`SHAREPOINT_URL_ARCHIVO_COMPARTIDO` para
el de archivo). Opcionales: `SHAREPOINT_NIVEL_LOG` y
`SHAREPOINT_CARPETA_PERFIL`. Diagnostico con
`SHAREPOINT_NIVEL_LOG=DEBUG`. `SHAREPOINT_URL_CARPETA_PRUEBAS` y
`SHAREPOINT_URL_ARCHIVO_COMPARTIDO` solo las usan estos tests; un proyecto
que importe la libreria pasa las URLs como parametros.

### Configuracion

El `.env` local es solo para los entrypoints propios (tests, login).
`.env` esta en `.gitignore`; se versiona `.env.example` con placeholders.

### Log de ejecucion

Cada corrida (tests o login) genera un log en la carpeta `logs/` del proyecto
(`sharepoint-%Y%m%d-%H%M%S.log`, conserva los 30 recientes) y duplica a
consola. Ante un fallo, leer el de mayor timestamp.

## Licencia

MIT
