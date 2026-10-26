import logging
import os
import shutil
from pathlib import Path

from sharepoint import (
    ClienteSharepoint,
    ExcepcionCarpetaNoEncontrada,
    ExcepcionNoAutenticado,
)
from sharepoint._log import configurar_log

log = logging.getLogger("sharepoint")

def _requerir_env(nombre: str) -> str:
    valor = os.environ.get(nombre)
    if not valor:
        raise SystemExit(f"Define {nombre} en el .env local (ver .env.example)")
    return valor

URL_CARPETA_BASE = _requerir_env("SHAREPOINT_URL_CARPETA_PRUEBAS")

# Carpetas subidas por test_upload_folders.
CARPETAS_A_DESCARGAR = ["carpeta_1", "carpeta_2", "carpeta_3"]
CARPETA_DESCARGA = Path(__file__).resolve().parent / "archivos" / "descarga"
CORREO_USUARIO = _requerir_env("SHAREPOINT_CORREO_USUARIO")
URL_INICIO = _requerir_env("SHAREPOINT_URL_INICIO")

def _limpiar_carpeta_descarga() -> Path:
    """Borra el contenido previo de download/ y lo recrea vacio."""
    shutil.rmtree(CARPETA_DESCARGA, ignore_errors=True)
    CARPETA_DESCARGA.mkdir(parents=True, exist_ok=True)
    log.info("Carpeta de descarga limpia: %s", CARPETA_DESCARGA)
    return CARPETA_DESCARGA

def principal() -> None:
    configurar_log()
    _limpiar_carpeta_descarga()
    try:
        with ClienteSharepoint(correo_usuario=CORREO_USUARIO, url_inicio=URL_INICIO, sin_ventana=False) as descargador:
            for nombre in CARPETAS_A_DESCARGAR:
                url_carpeta = f"{URL_CARPETA_BASE}/{nombre}"
                destino = CARPETA_DESCARGA
                descargador.descargar_carpeta(url_carpeta, str(destino))
                log.info("OK: %s descargada en: %s", nombre, destino)
    except ExcepcionCarpetaNoEncontrada as exc:
        log.error("Carpeta no encontrada: %s", exc)
        raise SystemExit(2) from exc
    except ExcepcionNoAutenticado as exc:
        log.error("Fallo autenticacion: %s", exc)
        raise SystemExit(3) from exc

if __name__ == "__main__":
    principal()
