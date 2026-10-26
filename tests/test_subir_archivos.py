import logging
import os
from pathlib import Path

from sharepoint import ClienteSharepoint, ExcepcionNoAutenticado
from sharepoint._log import configurar_log

log = logging.getLogger("sharepoint")

def _requerir_env(nombre: str) -> str:
    valor = os.environ.get(nombre)
    if not valor:
        raise SystemExit(f"Define {nombre} en el .env local (ver .env.example)")
    return valor

URL_CARPETA_DESTINO = _requerir_env("SHAREPOINT_URL_CARPETA_PRUEBAS")
CORREO_USUARIO = _requerir_env("SHAREPOINT_CORREO_USUARIO")
URL_INICIO = _requerir_env("SHAREPOINT_URL_INICIO")
CARPETA_SUBIDA = Path(__file__).resolve().parent / "archivos" / "subida"
ARCHIVOS_A_SUBIR = [str(p) for p in sorted(CARPETA_SUBIDA.glob("*.txt"))]

def principal() -> None:
    configurar_log()
    try:
        with ClienteSharepoint(correo_usuario=CORREO_USUARIO, url_inicio=URL_INICIO, sin_ventana=False) as cargador:
            cargador.subir_archivos({URL_CARPETA_DESTINO: ARCHIVOS_A_SUBIR})
            log.info("OK: carga de archivos completada")
    except ExcepcionNoAutenticado as exc:
        log.error("Fallo autenticacion: %s", exc)
        raise SystemExit(3) from exc

if __name__ == "__main__":
    principal()
