"""Operaciones de descarga desde SharePoint."""

import logging
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse
from zipfile import ZipFile

from playwright.sync_api import Error, Locator, Page

from ._excepciones import ExcepcionCarpetaNoEncontrada

log = logging.getLogger(__name__)

XPATH_BOTON_DESCARGAR = '//button[@data-automationid="downloadCommand"]'
XPATH_BOTON_MAS = '//button[@data-automationid="more"]'
XPATH_CARPETA_NO_ENCONTRADA = '//pre[text()="404 NOT FOUND"]'


def descargar_carpeta(pagina: Page, url_carpeta: str, ruta_local: str) -> None:
    """Descarga carpeta como zip con downloadCommand y extrae en destino."""
    carpeta_destino = Path(ruta_local)
    carpeta_destino.mkdir(parents=True, exist_ok=True)

    log.info("Navegando a carpeta: %s", url_carpeta)
    pagina.goto(url_carpeta, wait_until="load")

    carpeta_no_encontrada = pagina.locator(XPATH_CARPETA_NO_ENCONTRADA)
    if carpeta_no_encontrada.count() > 0:
        log.error("Carpeta no encontrada: %s", url_carpeta)
        raise ExcepcionCarpetaNoEncontrada(f"Carpeta no encontrada: {url_carpeta}")
    else:
        log.info("Carpeta encontrada, iniciando descarga...")

    boton_descargar = _resolver_boton_descarga(pagina)

    log.info("Descargando zip de carpeta")
    with pagina.expect_download(timeout=120000) as info_descarga:
        boton_descargar.click()

    resultado = info_descarga.value
    nombre_zip = resultado.suggested_filename or "sharepoint_folder.zip"

    log.debug("Descarga capturada: url=%s archivo=%s", resultado.url, nombre_zip)

    ruta_zip = carpeta_destino / nombre_zip
    resultado.save_as(ruta_zip)

    log.info("Zip guardado: %s (%.1f MB)", nombre_zip, ruta_zip.stat().st_size / 1e6)

    log.info("Extrayendo zip en: %s", carpeta_destino)
    with ZipFile(ruta_zip, "r") as archivo_zip:
        archivo_zip.extractall(carpeta_destino)

    ruta_zip.unlink(missing_ok=True)
    log.debug("Zip temporal borrado")
    log.info("Carpeta descargada en: %s", carpeta_destino)


def descargar_archivo_compartido(pagina: Page, url_archivo: str, ruta_local: str) -> None:
    """Descarga un archivo individual usando un vinculo compartido."""
    try:
        url_descarga = _construir_url_descarga_directa(url_archivo)
    except Exception:
        log.exception("Error al intentar construir el link de descarga directa.")
        return

    log.info("Descargando archivo: %s", url_descarga)

    with pagina.expect_download(timeout=60000) as info_descarga:
        try:
            pagina.goto(url_descarga)

            if pagina.title() == "Error": # El link no lleva a ningun archivo.
                log.info("El archivo no existe, se cancela la descarga.")
                return

        except Error: # SharePoint cierra la pagina al iniciar la descarga directa. La descarga continúa igualmente.
            pass

    resultado = info_descarga.value

    destino = Path(ruta_local)
    if destino.suffix:
        destino.parent.mkdir(parents=True, exist_ok=True)
        ruta_final = destino
    else:
        destino.mkdir(parents=True, exist_ok=True)
        ruta_final = destino / resultado.suggested_filename

    resultado.save_as(ruta_final)
    log.info("Archivo descargado en: %s (%.1f MB)", ruta_final, ruta_final.stat().st_size / 1e6)


def _resolver_boton_descarga(pagina: Page) -> Locator:
    """Retorna el boton Descargar, este en la barra o en el menu '...'.

    En ventanas angostas la barra colapsa botones al overflow y el
    downloadCommand ni siquiera existe en el DOM hasta abrir 'more'.
    """

    boton_descargar = pagina.locator(XPATH_BOTON_DESCARGAR)
    if boton_descargar.count() == 0:
        log.debug("Descargar no visible: abriendo menú '...'")
        pagina.locator(XPATH_BOTON_MAS).click()
        boton_descargar = pagina.locator(XPATH_BOTON_DESCARGAR)
    else:
        log.debug("Descargar directo en la barra")
    boton_descargar.wait_for(state="visible", timeout=10000)
    return boton_descargar


def _construir_url_descarga_directa(url_compartida: str) -> str:
    """Convierte un vinculo compartido al endpoint directo download.aspx."""
    parseada = urlparse(url_compartida)
    consulta = parse_qs(parseada.query)
    valor_d = consulta.get("d", [None])[0]
    if not valor_d:
        raise ValueError("El vinculo compartido no contiene el parametro 'd'.")

    hex_chars = "0123456789abcdefABCDEF"
    compacto = "".join(caracter for caracter in valor_d if caracter in hex_chars)
    if len(compacto) < 32:
        raise ValueError("No se pudo extraer un UniqueId valido desde el parametro 'd'.")

    compacto = compacto[-32:]
    guid = (
        f"{compacto[0:8]}-"
        f"{compacto[8:12]}-"
        f"{compacto[12:16]}-"
        f"{compacto[16:20]}-"
        f"{compacto[20:32]}"
    )
    guid_codificado = quote(guid, safe="")

    partes_ruta = [parte for parte in parseada.path.split("/") if parte]
    ruta_sitio = None
    if "sites" in partes_ruta:
        indice = partes_ruta.index("sites")
        if indice + 1 < len(partes_ruta):
            ruta_sitio = f"/sites/{partes_ruta[indice + 1]}"

    if not ruta_sitio:
        raise ValueError("No se pudo identificar '/sites/<nombre>' en el vinculo compartido.")

    url_descarga_directa = f"{parseada.scheme}://{parseada.netloc}{ruta_sitio}/_layouts/15/download.aspx?UniqueId={guid_codificado}"

    log.debug("URL directa construida: %s", url_descarga_directa)
    return url_descarga_directa
