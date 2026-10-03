from pathlib import Path

import logging
import os
import shutil
from ms365._logging import setup_logging
from ms365.sharepoint import NotAuthenticatedException, SharepointClient

log = logging.getLogger("ms365")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Define {name} en el .env local (ver .env.example)")
    return value


# Enlace compartido (?d=...) del archivo a descargar
# (Compartir > Copiar vinculo). Configurable por env MS365_TEST_SHARED_FILE_URL.
SHARED_FILE_URL = _require_env("MS365_TEST_SHARED_FILE_URL")
UPLOAD_DIR = Path(__file__).resolve().parent / "files" / "upload"
DOWNLOAD_DIR = Path(__file__).resolve().parent / "files" / "download"
USER_EMAIL = _require_env("MS365_USER_EMAIL")
HOME_URL = _require_env("MS365_HOME_URL")
HEADLESS = os.environ.get("MS365_HEADLESS", "false").strip().lower() in ("1", "true", "yes")


def _clean_download_dir() -> Path:
    """Borra el contenido previo de download/ y lo recrea vacio."""
    shutil.rmtree(DOWNLOAD_DIR, ignore_errors=True)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    log.info("Carpeta de descarga limpia: %s", DOWNLOAD_DIR)
    return DOWNLOAD_DIR


def main() -> None:
    setup_logging()
    _clean_download_dir()
    try:
        with SharepointClient(user_email=USER_EMAIL, home_url=HOME_URL, headless=HEADLESS) as client:
            client.download_single_file(SHARED_FILE_URL, str(DOWNLOAD_DIR))
            log.info("OK: descarga de archivo completada: %s", DOWNLOAD_DIR)
        expected = (UPLOAD_DIR / "file_1.txt").read_text(encoding="utf-8")
        downloaded = (DOWNLOAD_DIR / "file_1.txt").read_text(encoding="utf-8")
        if downloaded != expected:
            raise SystemExit("Contenido descargado distinto al original")
        log.info("OK: contenido verificado contra upload/file_1.txt")
    except NotAuthenticatedException as exc:
        log.error("Fallo autenticacion: %s", exc)
        raise SystemExit(3) from exc


if __name__ == "__main__":
    main()
