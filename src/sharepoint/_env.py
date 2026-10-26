import os
from pathlib import Path


def carpeta_perfil() -> Path:
    """Perfil de navegador dedicado, siempre fuera del proyecto.

    Se resuelve desde la variable SHAREPOINT_CARPETA_PERFIL; si no existe,
    usa %LOCALAPPDATA%/perfil_playwright_sharepoint.
    Local y no Roaming: el perfil es especifico de la maquina (cookies,
    locks, tamanio); Roaming lo sincronizaria por dominio.
    """
    base = os.environ.get("SHAREPOINT_CARPETA_PERFIL")
    if base:
        return Path(base)
    local = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    return Path(local) / "perfil_playwright_sharepoint"


def parametros_ventana(sin_ventana: bool) -> dict:
    """Solo tamano de ventana/viewport segun modo (sin channel).

    headed: no_viewport=True para que el contenido siga a la ventana
        (--window-size fija el tamaño inicial; --start-maximized no sirve
        porque no toca el viewport, que defaultea a 1280x720).
    headless: viewport 1920x1080 explicito (sin ventana no hay a quien seguir).
    """
    if sin_ventana:
        return {"viewport": {"width": 1920, "height": 1080}}
    return {
        "args": ["--window-size=1920,1080"],
        "no_viewport": True,
    }
