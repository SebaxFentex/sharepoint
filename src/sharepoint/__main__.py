"""Entry point para `python -m sharepoint` (login manual).

Uso:
    python -m sharepoint [URL_INICIO]

Precedencia: argumento > SHAREPOINT_URL_INICIO > error con mensaje.
"""

import argparse
import os


def renovar_autenticacion(argumentos: list[str] | None = None) -> None:
    """Resuelve la URL, configura logs y corre el login interactivo standalone."""
    from sharepoint._log import configurar_log
    from sharepoint.cliente import login_manual

    analizador = argparse.ArgumentParser(description="Login manual de SharePoint (MFA).")
    analizador.add_argument(
        "url_inicio",
        nargs="?",
        default=None,
        help="URL de inicio para validar la sesion (opcional si hay SHAREPOINT_URL_INICIO).",
    )
    opciones = analizador.parse_args(argumentos)

    url_inicio = opciones.url_inicio or os.environ.get("SHAREPOINT_URL_INICIO")
    if not url_inicio:
        raise SystemExit(
            "Falta la URL de inicio: pasala como argumento (`python -m sharepoint <URL>`) "
            "o define SHAREPOINT_URL_INICIO en el .env (ver .env.example)."
        )
    configurar_log()
    login_manual(url_inicio)


if __name__ == "__main__":
    renovar_autenticacion()
