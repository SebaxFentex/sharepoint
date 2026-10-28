# AGENTS.md — sharepoint

Guia para agentes (y humanos) que trabajan en este repo. Las reglas con
"porque" vienen de bugs reales; no relajarlas sin evidencia nueva.

## 1. Proyecto en 30 segundos

Libreria PAQUETE (`uv_build`, layout `src/`) para SharePoint Online con
Playwright + Chromium usando credenciales de usuario con MFA. No hay app en
Entra (restriccion corporativa: sin client_id propio; la via REST se probo
y el tenant la bloquea) — por eso todo pasa por el navegador.

Codigo, docstrings y `.env` en espanol (v0.3.0 rompio la API en ingles,
v0.4.0 renombro el paquete `ms365` a `sharepoint`; ver seccion 7).
SharePoint, Chromium, MFA y UniqueId son nombres propios y se conservan.

Stack: Python 3.14, `uv`. Entorno: `uv sync` + `uv run playwright install
chromium` (una vez; Chromium bundled, sin `channel`).

```text
src/sharepoint/
  __init__.py        # NullHandler + ClienteSharepoint + excepciones (NO re-exporta iniciar_sesion)
  _log.py       # configurar_log() + purgar_logs() — sin efectos al importar
  _env.py        # carpeta_perfil() y parametros_ventana() — rutas fijas
  _excepciones.py    # ExcepcionNoAutenticado, ExcepcionCarpetaNoEncontrada, ExcepcionArchivoNoEncontrado
  cliente.py         # ClienteSharepoint + login_manual + _login_interactivo
  __main__.py        # renovar_autenticacion() para `python -m sharepoint` (login manual)
  _subida.py         # subir_archivos / subir_carpetas (internas, reciben pagina)
  _descarga.py       # descargar_carpeta / descargar_archivo_compartido (internas)
ejecutables/
  login.bat          # login/refresco manual: `uv run ... python -m sharepoint`
  abrir_vscode.bat   # abre la raiz de la libreria en VS Code
tests/
  test_*.py          # e2e contra SHAREPOINT_URL_CARPETA_PRUEBAS (exigen MFA humano; sin env, fallan con mensaje)
  archivos/subida/      # fixtures locales (no usar rutas personales)
  archivos/descarga/    # salida de descargas: se limpia antes de cada test, ignorada por git
logs/                   # la crea configurar_log al correr tests o login (ignorada por git)
```

## 2. Arquitectura y API

- `ClienteSharepoint(correo_usuario, url_inicio, mostrar_navegador=False, pausa_ms=0, permitir_login_interactivo=False)`:
  context manager con sesion persistente de Chromium. `correo_usuario` y
  `url_inicio` son requeridos, sin defaults. La validacion de sesion ocurre
  al entrar al `with` (no al construir). Metodos publicos:
  `subir_archivos`, `subir_carpetas`, `descargar_carpeta`,
  `descargar_archivo_compartido`.
- `subir_carpetas` omite carpetas locales vacias. Para las no vacias,
  elimina primero la carpeta homonima de SharePoint con su contenido;
  conserva archivos homonimos.
- `cliente.login_manual(url_inicio=...) -> Path`: login standalone (sin
  cliente corriendo) con contexto temporal propio. Lo usa `python -m
  sharepoint` y `login.bat`.
- Ante sesion vencida con ventana + `permitir_login_interactivo`, el cliente
  reusa su propio contexto (`_login_interactivo`: pestaña nueva, Enter,
  cierre de pestaña) sin cerrar ni reabrir el navegador.
- `__main__.renovar_autenticacion()` (login manual): precedencia argumento >
  `SHAREPOINT_URL_INICIO` > error con mensaje (sin prompts).
- Orden de metodos en la clase: dunder → publicos → privados.
- UI del tenant en espanol: selectores `Cargar/Descargar/Reemplazar`.

## 3. Reglas inviolables

1. **Perfil con default fijo y override por env**: si existe
   `SHAREPOINT_CARPETA_PERFIL` se usa esa ruta; si no,
   `%LOCALAPPDATA%\perfil_playwright_sharepoint`. Sin params, sin perfiles del
   navegador (ver `_env.carpeta_perfil()`).
2. **`input()` solo en `cliente.py`** (`_login_interactivo`, `login_manual`),
   y solo en flujos con ventana. Ninguna ruta programada abre ventanas ni
   espera humanos: las corridas van al scheduler y deben fallar rapido
   (ver seccion 5).
3. **La libreria emite, el entrypoint configura**: `getLogger(__name__)` +
   `NullHandler` en el paquete; `configurar_log()` solo se llama desde
   `tests/*` y `__main__.renovar_autenticacion()`. Jamas configurar logging en
   `__init__` ni en constructores.
4. **`.bat` de proceso en `ejecutables/` invocando `uv run`** (nada de
   `python -c` con quoting). `abrir_vscode.bat` es utilitario: solo abre el
   editor y por eso no lleva `uv run`.
5. **Prohibido `click(force=True)`**: salta accionabilidad y produce clics
   fantasma (causo la intermitencia de la subida). Si un clic falla, que
   falle con diagnostico.
6. **Prohibido `timeout=0`**: espera infinita (causo el pegue eterno de la
   subida). Todo wait lleva deadline finito.
7. **Reintentos con estado fresco** (recarga de pagina), nunca sobre UI a
   medio abrir. Sin fallback a input oculto (se probo: no sirve).
8. **Un log por paso**: INFO auditable / DEBUG diagnostico / ERROR
   intervencion. URLs con UniqueId solo en DEBUG. Sin `print()` en libreria
   ni tests (el prompt al operador en `login_manual`/`_login_interactivo`
   es la unica excepcion).
9. **Sin re-exports en `__init__`** de `login_manual` (superficie minima:
   cliente + excepciones). Canonico: `from sharepoint.cliente import
   login_manual`. `python -m sharepoint` corre `__main__.py`, sin problema
   de doble instancia de runpy.
10. **Tamano de ventana centralizado** en `parametros_ventana()`: headed
    `no_viewport=True` (+ `--window-size` inicial), headless viewport
    1920×1080. `--start-maximized` no sirve (no toca el viewport).
11. **Nada especulativo**: sin abstracciones de un solo uso, sin params de
    "por si acaso". Lo muerto se borra (queda en git si se necesita).
12. **`.env` es del consumidor, no de la libreria**: `sharepoint` jamas
    carga dotenv. Los entrypoints propios leen del entorno: `tests/*` y
    `__main__` leen `SHAREPOINT_URL_INICIO`, `SHAREPOINT_CORREO_USUARIO`,
    `SHAREPOINT_URL_CARPETA_PRUEBAS`, `SHAREPOINT_URL_ARCHIVO_COMPARTIDO`
    (requeridas, fallan con mensaje si faltan) y `SHAREPOINT_NIVEL_LOG`,
    `SHAREPOINT_CARPETA_PERFIL` (opcionales, con default);
    `configurar_log()` ademas acepta nivel, prefijo y retencion por
    parametro. `.env` local esta en `.gitignore`, se versiona
    `.env.example` con placeholders.

## 4. Log de ejecucion

- Archivo + consola via `configurar_log()` (una linea al inicio de cada
  entrypoint). Nivel por env `SHAREPOINT_NIVEL_LOG` (default INFO).
- Archivos en la carpeta `logs/` del proyecto (utf-8). Prefijo y retencion
  llegan por parametro (`prefijo="sharepoint-"`, `conservar=30`); purga a los
  mas recientes.
- Cada corrida genera su propio log: ante un fallo, leer **el de mayor
  timestamp**, nunca uno viejo.

## 5. Scheduler y codigos de salida

- `0` OK · `2` carpeta inexistente · `3` autenticacion · `4` archivo
  compartido inexistente (corre `ejecutables/login.bat` en sesion
  interactiva y reintenta solo el 3).
- La tarea corre como el **mismo usuario Windows** duenio del perfil, con
  `mostrar_navegador=False`. Sesion muerta = exit 3, sin reintento automatico
  (con MFA no hay refresh desatendido posible). Nunca programar tareas con
  ventana: una sesion vencida con navegador visible espera un humano que no
  hay y cuelga el slot del scheduler.
- Cada proyecto consumidor necesita su propio `ejecutables/login.bat`
  con la URL como argumento (cero variables en produccion):
  ```bat
  @echo off
  cd /d "%~dp0..\python_<nombre>"
  uv run python -m sharepoint https://empresa.sharepoint.com/.../Home.aspx
  ```
  (Alternativa: `SHAREPOINT_URL_INICIO` en su `.env`.) El `login.bat` de la
  libreria usa el `.env` de desarrollo y no sirve en produccion.

## 6. Verificacion antes de dar por hecho

1. `py_compile` + import smoke (con `RuntimeWarning` como error para `-m`).
2. Logica nueva con dobles falsos **sin browser**. El e2e exige MFA humano.
3. `uv build` OK.
4. Greps de guardia: cero `force=True`, `input(` solo en
   `cliente.py`, cero `timeout=0`, cero `set_input_files` en el flujo
   de subida, cero `load_dotenv` y cero `cwd(` en `src/`, cero
   `autenticacion` en el repo.

## 7. Historial de rupturas

- **v0.3.0 (2026-10-26)**: renombre total a espanol (normativa Tigo).
  `SharepointClient` → `ClienteSharepoint`, `upload_files` →
  `subir_archivos`, `login` → `iniciar_sesion`, `MS365_USER_EMAIL` →
  `MS365_CORREO_USUARIO`, etc.
- **v0.4.0 (2026-10-26)**: el paquete `ms365` pasa a llamarse `sharepoint`.
  `ms365.sharepoint` → `sharepoint` (`from sharepoint import
  ClienteSharepoint`, `python -m sharepoint`),
  `MS365_*` → `SHAREPOINT_*`, datos locales
  `%LOCALAPPDATA%/programas_python/ms365` →
  `%LOCALAPPDATA%/programas_python/sharepoint`. Los proyectos que usaban los
  nombres viejos deben migrar.
- **v0.5.0 (2026-10-26)**: conceptos tecnicos en ingles (normativa Tigo,
  seccion 1.2 de excepciones): `_registro` → `_log` (`configurar_log`,
  `purgar_logs`, `SHAREPOINT_NIVEL_LOG`…), `_entorno` → `_env`.
- **v0.5.1 (2026-10-26)**: los logs de desarrollo salen de `%LOCALAPPDATA%`
  a la carpeta `logs/` del proyecto (ignorada por git); el perfil del
  navegador sigue en `%LOCALAPPDATA%/programas_python/sharepoint`.
- **v0.5.2 (2026-10-26)**: `carpeta_aplicacion` se fusiona en
  `carpeta_perfil`; la ruta del perfil acepta override por
  `SHAREPOINT_CARPETA_PERFIL` y el default pasa a
  `%LOCALAPPDATA%/perfil_playwright_sharepoint`.
- **v0.6.0 (2026-10-26)**: `SHAREPOINT_SIN_VENTANA` pasa a
  `SHAREPOINT_MOSTRAR_NAVEGADOR` con valores estrictos `True`/`False`
  (cualquier otro valor detiene el test con mensaje); la logica se invierte
  (`mostrar` en vez de `sin ventana`).
- **v0.7.0 (2026-10-26)**: `SHAREPOINT_MOSTRAR_NAVEGADOR` deja de ser env
  (los tests pasan `sin_ventana=False` directo al cliente);
  `SHAREPOINT_PREFIJO_LOG` y `SHAREPOINT_MAX_LOGS` pasan a parametros de
  `configurar_log()` con defaults.
- **v0.8.0 (2026-10-26)**: manejo de sesion vencida en produccion.
  `sin_ventana` pasa a `mostrar_navegador` (logica invertida, mismo default
  efectivo); la validacion se mueve de `__init__` a `__enter__`;
  `ExcepcionNoAutenticado`/`ExcepcionCarpetaNoEncontrada` llevan
  `codigo_salida` (3/2) y mensaje agnostico; nuevo opt-in
  `permitir_login_interactivo` (default False) para re-login con ventana;
  plantilla del `login.bat` del consumidor en README/AGENTS.
- **v0.9.0 (2026-10-26)**: `autenticacion.py` se elimina. El login vive en
  `cliente.py`: `_login_interactivo` reusa el propio contexto (sin
  cerrar/reabrir navegadores) y `login_manual` atiende el login standalone;
  entrypoint `python -m sharepoint` (`__main__.py`) y `login.bat`
  actualizado. Sin compatibilidad heredada.
- **v1.0.0 (2026-10-26)**: primera version estable. `principal()` pasa a
  `renovar_autenticacion()`; mensaje de sesion vencida completo; `import
  os` sin uso eliminado; `destino: Path` tipado; `.env.example` con la
  carpeta de perfil comentada (la forma activa rompia rutas con
  `%...%`); regla 12 con todas las lecturas de entorno.
- **v0.9.1 (2026-10-26)**: `principal()` acepta la URL como argumento
  opcional (precedencia: argumento > `SHAREPOINT_URL_INICIO` > error, sin
  prompts); produccion queda sin variables obligatorias.
- **v1.1.0 (2026-10-26)**: contrato de errores y cierre de recursos.
  `descargar_archivo_compartido` propaga `ValueError` y lanza
  `ExcepcionArchivoNoEncontrado` (codigo 4) si el archivo no existe (antes
  retornaba en silencio); `__enter__` cierra el navegador si falla la
  validacion; `cerrar()` es idempotente por pagina y detiene el driver
  (`playwright.stop()`), que antes quedaba vivo; `_esperar_fin_subida`
  distingue "sin dialogo" (DEBUG) de "reemplazo fallido" (WARNING);
  `_abrir_contexto` movido al bloque privado (orden dunder → publicos →
  privados); regla 4 del AGENTS precisa el caso de `abrir_vscode.bat`.
