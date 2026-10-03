import logging
import os
from pathlib import Path

from ms365._logging import setup_logging
from ms365.sharepoint import NotAuthenticatedException, SharepointClient


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Define {name} en el .env local (ver .env.example)")
    return value


TARGET_FOLDER_URL = _require_env("MS365_TEST_FOLDER_URL")
USER_EMAIL = _require_env("MS365_USER_EMAIL")
HOME_URL = _require_env("MS365_HOME_URL")
UPLOAD_DIR = Path(__file__).resolve().parent / "files" / "upload"
# Carpetas de primer nivel (folder_1, folder_2 con folder_21 anidada,
# folder_3 vacia, esta ultima se omite por estar vacia).
FOLDERS_TO_UPLOAD = [str(p) for p in sorted(UPLOAD_DIR.iterdir()) if p.is_dir()]
HEADLESS = os.environ.get("MS365_HEADLESS", "false").strip().lower() in ("1", "true", "yes")

log = logging.getLogger("ms365")


def main() -> None:
    setup_logging()
    try:
        with SharepointClient(user_email=USER_EMAIL, home_url=HOME_URL, headless=HEADLESS) as uploader:
            uploader.upload_folders({TARGET_FOLDER_URL: FOLDERS_TO_UPLOAD})
            log.info("OK: carga de carpetas completada")
    except NotAuthenticatedException as exc:
        log.error("Fallo autenticacion: %s", exc)
        raise SystemExit(3) from exc


if __name__ == "__main__":
    main()
