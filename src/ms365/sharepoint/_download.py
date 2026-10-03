"""Operaciones de descarga desde SharePoint."""

import logging
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse
from zipfile import ZipFile

from playwright.sync_api import Error, Locator, Page

from ._exceptions import FolderNotFoundException

log = logging.getLogger(__name__)

xpath_download_button = '//button[@data-automationid="downloadCommand"]'
xpath_more_button = '//button[@data-automationid="more"]'
xpath_folder_not_found = '//pre[text()="404 NOT FOUND"]'


def download_folder(page: Page, folder_url: str, local_path: str) -> None:
    """Descarga carpeta como zip con downloadCommand y extrae en destino."""
    destination_dir = Path(local_path)
    destination_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"Navegando a carpeta: {folder_url}")
    page.goto(folder_url, wait_until="load")

    folder_not_found = page.locator(xpath_folder_not_found)
    if folder_not_found.count() > 0:
        log.error("Carpeta no encontrada: %s", folder_url)
        raise FolderNotFoundException(f"Carpeta no encontrada: {folder_url}")
    else:
        log.info("Carpeta encontrada, iniciando descarga...")

    download_button = _resolve_download_button(page)

    log.info("Descargando zip de carpeta")
    with page.expect_download(timeout=120000) as download_info:
        download_button.click()

    download_result = download_info.value
    zip_name = download_result.suggested_filename or "sharepoint_folder.zip"

    log.debug("Descarga capturada: url=%s archivo=%s", download_result.url, zip_name)

    zip_path = destination_dir / zip_name
    download_result.save_as(zip_path)

    log.info("Zip guardado: %s (%.1f MB)", zip_name, zip_path.stat().st_size / 1e6)

    log.info(f"Extrayendo zip en: {destination_dir}")
    with ZipFile(zip_path, "r") as zip_file:
        zip_file.extractall(destination_dir)

    zip_path.unlink(missing_ok=True)
    log.debug("Zip temporal borrado")
    log.info(f"Carpeta descargada en: {destination_dir}")


def download_single_file(page: Page, file_url: str, local_path: str) -> None:
    """Descarga un archivo individual usando un vinculo compartido."""
    try:
        download_url = _build_direct_download_url(file_url)
    except Exception:
        log.exception("Error al intentar construir el link de descarga directa.")
        return

    log.info(f"Descargando archivo: {download_url}")

    with page.expect_download(timeout=60000) as download_info:
        try:
            page.goto(download_url)

            if page.title() == "Error": # El link no lleva a ningun archivo.
                log.info("El archivo no existe, se cancela la descarga.")
                return
        
        except Error: # SharePoint cierra la pagina al iniciar la descarga directa. La descarga continúa igualmente.
            pass

    download_result = download_info.value

    destination = Path(local_path)
    if destination.suffix:
        destination.parent.mkdir(parents=True, exist_ok=True)
        final_path = destination
    else:
        destination.mkdir(parents=True, exist_ok=True)
        final_path = destination / download_result.suggested_filename

    download_result.save_as(final_path)
    log.info("Archivo descargado en: %s (%.1f MB)", final_path, final_path.stat().st_size / 1e6)


def _resolve_download_button(page: Page) -> Locator:
    """Retorna el boton Descargar, este en la barra o en el menu '...'.

    En ventanas angostas la barra colapsa botones al overflow y el
    downloadCommand ni siquiera existe en el DOM hasta abrir 'more'.
    """

    download_button = page.locator(xpath_download_button)
    if download_button.count() == 0:
        log.debug("Descargar no visible: abriendo menú '...'")
        page.locator(xpath_more_button).click()
        download_button = page.locator(xpath_download_button)
    else:
        log.debug("Descargar directo en la barra")
    download_button.wait_for(state="visible", timeout=10000)
    return download_button


def _build_direct_download_url(shared_file_url: str) -> str:
    """Convierte un vinculo compartido al endpoint directo download.aspx."""
    parsed = urlparse(shared_file_url)
    query = parse_qs(parsed.query)
    d_value = query.get("d", [None])[0]
    if not d_value:
        raise ValueError("El vinculo compartido no contiene el parametro 'd'.")

    hex_chars = "0123456789abcdefABCDEF"
    compact = "".join(ch for ch in d_value if ch in hex_chars)
    if len(compact) < 32:
        raise ValueError("No se pudo extraer un UniqueId valido desde el parametro 'd'.")

    compact = compact[-32:]
    guid = (
        f"{compact[0:8]}-"
        f"{compact[8:12]}-"
        f"{compact[12:16]}-"
        f"{compact[16:20]}-"
        f"{compact[20:32]}"
    )
    encoded_guid = quote(guid, safe="")

    path_parts = [part for part in parsed.path.split("/") if part]
    site_path = None
    if "sites" in path_parts:
        idx = path_parts.index("sites")
        if idx + 1 < len(path_parts):
            site_path = f"/sites/{path_parts[idx + 1]}"

    if not site_path:
        raise ValueError("No se pudo identificar '/sites/<nombre>' en el vinculo compartido.")

    direct_download_url = f"{parsed.scheme}://{parsed.netloc}{site_path}/_layouts/15/download.aspx?UniqueId={encoded_guid}"

    log.debug("URL directa construida: %s", direct_download_url)
    return direct_download_url
