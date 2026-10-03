"""Bootstrap interactivo de sesion (primer login o refresco).

Nunca llamar desde rutas programadas: abre el navegador y espera input humano.
Las corridas desatendidas deben fallar rapido con NotAuthenticatedException.
"""

import logging
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

from ._base import browser_window_kwargs, profile_dir

log = logging.getLogger(__name__)


def login(home_url: str) -> Path:
    """Abre el perfil de navegador dedicado en headed para login manual con MFA.

    El perfil siempre es %LOCALAPPDATA%/programas_python/ms365/perfil_navegador_playwright
    (ver ms365.sharepoint._base). No usa perfiles del navegador.

    Args:
        home_url: Pagina a abrir para autenticarse (requerido, sin default).

    Returns:
        Ruta del perfil utilizado.
    """
    target = profile_dir()
    log.info("Abriendo perfil para login: %s", target)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(target),
            headless=False,
            **browser_window_kwargs(headless=False),
        )
        ctx.new_page().goto(home_url, wait_until="domcontentloaded")
        print("Inicia sesion con tu usuario + MFA en el navegador.")
        input("Cuando veas el sitio, pulsa Enter aqui... ")
        ctx.close()
    log.info(f"Sesion guardada en: {target}")
    return target


def main() -> None:
    """Entry point para `python -m ms365.sharepoint.auth` y scripts/login.bat."""
    from ms365._logging import setup_logging

    setup_logging()
    home_url = os.environ.get("MS365_HOME_URL")
    if not home_url:
        raise SystemExit("Define MS365_HOME_URL en el .env local (ver .env.example)")
    login(home_url=home_url)


if __name__ == "__main__":
    main()
