import logging
import os
import shutil
from pathlib import Path

from sharepoint import ClienteSharepoint, ExcepcionNoAutenticado
from sharepoint._log import configurar_log

log = logging.getLogger("sharepoint")

def _requerir_env(nombre: str) -> str:
    valor = os.environ.get(nombre)
    if not valor:
        raise SystemExit(f"Define {nombre} en el .env local (ver .env.example)")
    return valor

# Enlace compartido (?d=...) del archivo a descargar
# (Compartir > Copiar vinculo). Configurable por env SHAREPOINT_URL_ARCHIVO_COMPARTIDO.
URL_ARCHIVO_COMPARTIDO = _requerir_env("SHAREPOINT_URL_ARCHIVO_COMPARTIDO")
CARPETA_SUBIDA = Path(__file__).resolve().parent / "archivos" / "subida"
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
        with ClienteSharepoint(correo_usuario=CORREO_USUARIO, url_inicio=URL_INICIO, sin_ventana=False) as cliente:
            cliente.descargar_archivo_compartido(URL_ARCHIVO_COMPARTIDO, str(CARPETA_DESCARGA))
            log.info("OK: descarga de archivo completada: %s", CARPETA_DESCARGA)
        esperado = (CARPETA_SUBIDA / "archivo_1.txt").read_text(encoding="utf-8")
        descargado = (CARPETA_DESCARGA / "archivo_1.txt").read_text(encoding="utf-8")
        if descargado != esperado:
            raise SystemExit("Contenido descargado distinto al original")
        log.info("OK: contenido verificado contra upload/archivo_1.txt")
    except ExcepcionNoAutenticado as exc:
        log.error("Fallo autenticacion: %s", exc)
        raise SystemExit(3) from exc

if __name__ == "__main__":
    principal()
