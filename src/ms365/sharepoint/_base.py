import os
from pathlib import Path


def app_dir() -> Path:
    """Raiz de datos del programa, siempre en Local. Sin parametros ni overrides.

    Local y no Roaming: perfil y logs son especificos de la maquina (cookies,
    locks, tamanio); Roaming los sincronizaria por dominio.
    """
    base = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    return Path(base) / "programas_python" / "ms365"


def profile_dir() -> Path:
    """Perfil de navegador dedicado (ver app_dir)."""
    return app_dir() / "perfil_navegador_playwright"


def browser_window_kwargs(headless: bool) -> dict:
    """Solo tamano de ventana/viewport segun modo (sin channel).

    headed: no_viewport=True para que el contenido siga a la ventana
        (--window-size fija el tamaño inicial; --start-maximized no sirve
        porque no toca el viewport, que defaultea a 1280x720).
    headless: viewport 1920x1080 explicito (sin ventana no hay a quien seguir).
    """
    if headless:
        return {"viewport": {"width": 1920, "height": 1080}}
    return {
        "args": ["--window-size=1920,1080"],
        "no_viewport": True,
    }
