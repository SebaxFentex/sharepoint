"""Operaciones de carga a SharePoint."""

import logging
from pathlib import Path

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

log = logging.getLogger(__name__)

xpath_create_or_upload_button = '//button[@data-automationid="newCommand"]'
xpath_upload_file_button = '//button[@data-automationid="uploadFile"]'
xpath_upload_folder_button = '//button[@data-automationid="uploadFolder"]'


def upload_files(
    page: Page,
    user_email: str,
    files_by_folder: dict[str, list[str]],
) -> None:
    for folder_url, file_paths in files_by_folder.items():
        _upload_files_to_folder(page, user_email, folder_url, file_paths)


def upload_folders(
    page: Page,
    user_email: str,
    folders_by_folder: dict[str, list[str]],
) -> None:
    for folder_url, folder_paths in folders_by_folder.items():
        _upload_folders_to_folder(page, user_email, folder_url, folder_paths)


def _goto_folder(page: Page, user_email: str, folder_url: str) -> None:
    """Navega a la carpeta destino y descarta el popup de cuenta si aparece."""
    log.info(f"Navegando a SharePoint: {folder_url}")
    page.goto(folder_url)

    user_btn = page.locator(f'small[text="{user_email}"]')
    if user_btn.is_visible():
        user_btn.click()
        log.debug("Popup de cuenta descartado")


def _delete_existing_folder(page: Page, folder_name: str) -> None:
    """Elimina una carpeta homonima del destino; conserva archivos."""
    list_page = page.locator('div[data-automationid="list-page"]')
    list_page.wait_for(state="visible", timeout=30000)
    rows = list_page.locator(":scope > div")

    for index in range(rows.count()):
        row = rows.nth(index)
        name_spans = row.locator('div[data-automationid="field-LinkFilename"] > span')
        span_count = name_spans.count()
        if span_count == 0:
            continue
        if span_count != 1:
            raise RuntimeError(f"No se pudo identificar el nombre del elemento: {folder_name}")
        if name_spans.inner_text().strip() != folder_name:
            continue

        icon = row.locator('div[data-automationid="field-DocIcon"]')
        children = icon.locator(":scope > *")
        if children.count() != 1:
            raise RuntimeError(f"No se pudo identificar el tipo del elemento: {folder_name}")
        if icon.locator(":scope > img").count() == 1:
            log.debug("Existe un archivo con el nombre %s; se conserva", folder_name)
            continue
        if icon.locator(':scope > div:not([alt])').count() != 1:
            raise RuntimeError(f"No se pudo identificar el tipo del elemento: {folder_name}")

        selection_index = row.get_attribute("data-selection-index")
        if selection_index is None:
            raise RuntimeError(f"No se pudo identificar la fila de la carpeta: {folder_name}")

        log.info("Eliminando carpeta existente: %s", folder_name)
        selection_cell = row.locator('[data-automationid^="row-selection-"]')
        selection_cell.wait_for(state="visible", timeout=10000)
        selection_cell.click()

        delete_button = page.locator('button[data-automationid="deleteCommand"]')
        delete_button.wait_for(state="visible", timeout=10000)
        delete_button.click()

        confirm_button = page.locator('button[data-automationid="confirmbutton"]')
        confirm_button.wait_for(state="visible", timeout=10000)
        confirm_button.click()
        deleted_row = list_page.locator(
            f':scope > div[data-selection-index="{selection_index}"]'
        )
        deleted_row.wait_for(state="detached", timeout=30000)
        log.info("Carpeta existente eliminada: %s", folder_name)
        return

    log.debug("No hay carpeta existente para eliminar: %s", folder_name)


def _set_upload_files(
    page: Page,
    user_email: str,
    kind: str,
    paths: list[str],
    folder_url: str,
    attempts: int = 3,
) -> None:
    """Sube rutas recargando la pagina en cada intento (el timing es flaky).

    Por intento: recarga carpeta -> abre menu -> file chooser (5s).
    Sin fallback a input oculto: no sirve. Agotados los intentos
    propaga el ultimo error.
    """
    last_error: PlaywrightTimeoutError | None = None
    for i in range(1, attempts + 1):
        if i > 1:
            log.debug("Recargando carpeta (intento %d)", i)
        _goto_folder(page, user_email, folder_url)

        upload_btn = page.locator(xpath_create_or_upload_button)
        upload_btn.wait_for(state="visible", timeout=30000)
        upload_btn.click()

        if kind == "file":
            pick_btn = page.locator(xpath_upload_file_button)
        else:
            pick_btn = page.locator(xpath_upload_folder_button)
        pick_btn.wait_for(state="visible", timeout=10000)
        log.debug("Menú Cargar abierto (%s)", kind)

        try:
            with page.expect_file_chooser(timeout=5000) as fc_info:
                pick_btn.click()
            fc_info.value.set_files(paths)
            log.debug("File chooser detectado (intento %d)", i)
            return
        except PlaywrightTimeoutError as e:
            last_error = e
            log.warning("Intento %d/%d sin chooser", i, attempts)
    assert last_error is not None
    raise last_error


def _wait_upload_done(page: Page, verb: str) -> None:
    """Espera el toast de progreso y confirma Reemplazar si aparece."""
    progress_toast = page.get_by_role("alert").filter(has_text=verb)
    progress_toast.wait_for(state="attached", timeout=10000)
    progress_toast.wait_for(state="detached", timeout=120000)

    try:
        replace_btn = page.get_by_role("button", name="Reemplazar")
        replace_btn.wait_for(state="attached", timeout=5000)
        replace_btn.click()
        log.info("Reemplazando...")
        progress_toast.wait_for(state="attached", timeout=5000)
        progress_toast.wait_for(state="detached", timeout=120000)
    except Exception:
        pass


def _upload_files_to_folder(
    page: Page,
    user_email: str,
    folder_url: str,
    file_paths: list[str],
) -> None:
    """Sube una lista de archivos a la carpeta destino."""
    normalized = [str(Path(fp)) for fp in file_paths]

    log.info(f"Subiendo {len(normalized)} archivo(s)")
    _set_upload_files(page, user_email, "file", normalized, folder_url)
    _wait_upload_done(page, "Cargando")
    log.info("Archivos subidos")


def _upload_folders_to_folder(
    page: Page,
    user_email: str,
    folder_url: str,
    folder_paths: list[str],
) -> None:
    """Elimina una carpeta homonima y sube cada carpeta desde pagina fresca."""
    normalized = [str(Path(fp)) for fp in folder_paths]

    for folder_path in normalized:
        folder = Path(folder_path)
        folder_name = folder.name
        if not any(folder.iterdir()):
            log.info("Carpeta vacía; se omite: %s", folder_name)
            continue

        log.info("Subiendo carpeta: %s", folder_name)
        _goto_folder(page, user_email, folder_url)
        _delete_existing_folder(page, folder_name)
        _set_upload_files(page, user_email, "folder", [folder_path], folder_url)
        _wait_upload_done(page, "Actualizando")
        log.info("Carpeta subida")
