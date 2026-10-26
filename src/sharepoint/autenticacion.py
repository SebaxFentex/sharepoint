"""Bootstrap interactivo de sesion (primer inicio de sesion o refresco).

Nunca llamar desde rutas programadas: abre el navegador y espera input humano.
Las corridas desatendidas deben fallar rapido con ExcepcionNoAutenticado.
"""

import logging
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

from ._env import carpeta_perfil, parametros_ventana

log = logging.getLogger(__name__)


def iniciar_sesion(url_inicio: str) -> Path:
    """Abre el perfil de navegador dedicado en headed para login manual con MFA.

    El perfil siempre es %LOCALAPPDATA%/programas_python/sharepoint/perfil_navegador_playwright
    (ver sharepoint._env). No usa perfiles del navegador.

    Args:
        url_inicio: Pagina a abrir para autenticarse (requerido, sin default).

    Returns:
        Ruta del perfil utilizado.
    """
    destino = carpeta_perfil()
    log.info("Abriendo perfil para login: %s", destino)
    with sync_playwright() as p:
        contexto = p.chromium.launch_persistent_context(
            user_data_dir=str(destino),
            headless=False,
            **parametros_ventana(sin_ventana=False),
        )
        contexto.new_page().goto(url_inicio, wait_until="domcontentloaded")
        print("Inicia sesion con tu usuario + MFA en el navegador.")
        input("Cuando veas el sitio, pulsa Enter aqui... ")
        contexto.close()
    log.info("Sesion guardada en: %s", destino)
    return destino


def principal() -> None:
    """Entry point para `python -m sharepoint.autenticacion` y ejecutables/login.bat."""
    from sharepoint._log import configurar_log

    configurar_log()
    url_inicio = os.environ.get("SHAREPOINT_URL_INICIO")
    if not url_inicio:
        raise SystemExit("Define SHAREPOINT_URL_INICIO en el .env local (ver .env.example)")
    iniciar_sesion(url_inicio=url_inicio)


if __name__ == "__main__":
    principal()
