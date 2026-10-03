"""Configuracion de logging para los entrypoints (tests, scripts).

La libreria solo emite registros (logging.getLogger(__name__)); este modulo
solo actua cuando alguien lo llama. Nunca se ejecuta al importar.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

DEFAULT_LOG_FILE_PREFIX = "ms365-"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_MAX_LOG_FILES = 30


def logs_dir() -> Path:
    """Carpeta logs bajo app_dir (misma raiz que el perfil)."""
    from ms365.sharepoint._base import app_dir

    return app_dir() / "logs"


def prune_logs(
    directory: Path,
    keep: int = DEFAULT_MAX_LOG_FILES,
    prefix: str = DEFAULT_LOG_FILE_PREFIX,
) -> None:
    """Borra los .log mas viejos dejando los `keep` recientes (por nombre)."""
    files = sorted(directory.glob(f"{prefix}*.log"))
    for old in files[: max(0, len(files) - keep)]:
        old.unlink(missing_ok=True)


def setup_logging(level: str | None = None) -> logging.Logger:
    """Configura archivo + consola para el logger "ms365". Idempotente.

    Nivel: parametro > env MS365_LOG_LEVEL > DEFAULT_LOG_LEVEL. Valor invalido cae a DEFAULT_LOG_LEVEL.
    Prefijo y retencion salen directo del env (solo entrypoints de este repo;
    la libreria no los lee por su cuenta): MS365_LOG_FILE_PREFIX
    (default "ms365-"), MS365_MAX_LOG_FILES (default 30, debe ser entero).
    El NullHandler que la libreria agrega en ms365/__init__.py no cuenta
    como configuracion: se ignora a proposito para poder configurarlo aqui.
    """
    resolved = (level or os.environ.get("MS365_LOG_LEVEL", DEFAULT_LOG_LEVEL)).upper()
    if resolved not in logging.getLevelNamesMapping():
        resolved = DEFAULT_LOG_LEVEL

    prefix = os.getenv("MS365_LOG_FILE_PREFIX", DEFAULT_LOG_FILE_PREFIX)
    keep = int(os.getenv("MS365_MAX_LOG_FILES", str(DEFAULT_MAX_LOG_FILES)))

    logger = logging.getLogger("ms365")
    if any(not isinstance(h, logging.NullHandler) for h in logger.handlers):
        return logger

    directory = logs_dir()
    directory.mkdir(parents=True, exist_ok=True)
    log_file = directory / f"{prefix}{datetime.now():%Y%m%d-%H%M%S}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.setLevel(resolved)

    prune_logs(directory, keep=keep, prefix=prefix)
    logger.info("Log en: %s (nivel %s)", log_file, resolved)
    return logger
