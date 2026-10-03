import logging
import os
import shutil
from pathlib import Path

from ms365._logging import setup_logging
from ms365.sharepoint import (
    FolderNotFoundException,
    NotAuthenticatedException,
    SharepointClient,
)

def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Define {name} en el .env local (ver .env.example)")
    return value


BASE_FOLDER_URL = _require_env("MS365_TEST_FOLDER_URL")

# Carpetas subidas por test_upload_folders.
FOLDERS_TO_DOWNLOAD = ["folder_1", "folder_2", "folder_3"]
DOWNLOAD_DIR = Path(__file__).resolve().parent / "files" / "download"
USER_EMAIL = _require_env("MS365_USER_EMAIL")
HOME_URL = _require_env("MS365_HOME_URL")
HEADLESS = os.environ.get("MS365_HEADLESS", "false").strip().lower() in ("1", "true", "yes")

log = logging.getLogger("ms365")


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
        with SharepointClient(user_email=USER_EMAIL, home_url=HOME_URL, headless=HEADLESS) as downloader:
            for name in FOLDERS_TO_DOWNLOAD:
                folder_url = f"{BASE_FOLDER_URL}/{name}"
                dest = DOWNLOAD_DIR
                downloader.download_folder(folder_url, str(dest))
                log.info("OK: %s descargada en: %s", name, dest)
    except FolderNotFoundException as exc:
        log.error("Carpeta no encontrada: %s", exc)
        raise SystemExit(2) from exc
    except NotAuthenticatedException as exc:
        log.error("Fallo autenticacion: %s", exc)
        raise SystemExit(3) from exc


if __name__ == "__main__":
    main()
