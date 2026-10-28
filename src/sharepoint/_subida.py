"""Operaciones de subida a SharePoint."""

import logging
from pathlib import Path
from typing import Literal

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

log = logging.getLogger(__name__)

XPATH_BOTON_CREAR_O_SUBIR = '//button[@data-automationid="newCommand"]'
XPATH_BOTON_SUBIR_ARCHIVO = '//button[@data-automationid="uploadFile"]'
XPATH_BOTON_SUBIR_CARPETA = '//button[@data-automationid="uploadFolder"]'


def subir_archivos(
    pagina: Page,
    correo_usuario: str,
    archivos_por_carpeta: dict[str, list[str]],
) -> None:
    for url_carpeta, rutas_archivos in archivos_por_carpeta.items():
        _subir_archivos_a_carpeta(pagina, correo_usuario, url_carpeta, rutas_archivos)


def subir_carpetas(
    pagina: Page,
    correo_usuario: str,
    carpetas_por_carpeta: dict[str, list[str]],
) -> None:
    for url_carpeta, rutas_carpetas in carpetas_por_carpeta.items():
        _subir_carpetas_a_carpeta(pagina, correo_usuario, url_carpeta, rutas_carpetas)


def _ir_a_carpeta(pagina: Page, correo_usuario: str, url_carpeta: str) -> None:
    """Navega a la carpeta destino y descarta el popup de cuenta si aparece."""
    log.info("Navegando a SharePoint: %s", url_carpeta)
    pagina.goto(url_carpeta)

    boton_usuario = pagina.locator(f'small[text="{correo_usuario}"]')
    if boton_usuario.is_visible():
        boton_usuario.click()
        log.debug("Popup de cuenta descartado")


def _eliminar_carpeta_existente(pagina: Page, nombre_carpeta: str) -> None:
    """Elimina una carpeta homonima del destino; conserva archivos."""
    pagina_listado = pagina.locator('div[data-automationid="list-page"]')
    pagina_listado.wait_for(state="visible", timeout=30000)
    filas = pagina_listado.locator(":scope > div")

    for indice in range(filas.count()):
        fila = filas.nth(indice)
        nombres = fila.locator('div[data-automationid="field-LinkFilename"] > span')
        conteo_nombres = nombres.count()
        if conteo_nombres == 0:
            continue
        if conteo_nombres != 1:
            raise RuntimeError(f"No se pudo identificar el nombre del elemento: {nombre_carpeta}")
        if nombres.inner_text().strip() != nombre_carpeta:
            continue

        icono = fila.locator('div[data-automationid="field-DocIcon"]')
        hijos = icono.locator(":scope > *")
        if hijos.count() != 1:
            raise RuntimeError(f"No se pudo identificar el tipo del elemento: {nombre_carpeta}")
        if icono.locator(":scope > img").count() == 1:
            log.debug("Existe un archivo con el nombre %s; se conserva", nombre_carpeta)
            continue
        if icono.locator(':scope > div:not([alt])').count() != 1:
            raise RuntimeError(f"No se pudo identificar el tipo del elemento: {nombre_carpeta}")

        indice_seleccion = fila.get_attribute("data-selection-index")
        if indice_seleccion is None:
            raise RuntimeError(f"No se pudo identificar la fila de la carpeta: {nombre_carpeta}")

        log.info("Eliminando carpeta existente: %s", nombre_carpeta)
        celda_seleccion = fila.locator('[data-automationid^="row-selection-"]')
        celda_seleccion.wait_for(state="visible", timeout=10000)
        celda_seleccion.click()

        boton_eliminar = pagina.locator('button[data-automationid="deleteCommand"]')
        boton_eliminar.wait_for(state="visible", timeout=10000)
        boton_eliminar.click()

        boton_confirmar = pagina.locator('button[data-automationid="confirmbutton"]')
        boton_confirmar.wait_for(state="visible", timeout=10000)
        boton_confirmar.click()
        fila_eliminada = pagina_listado.locator(
            f':scope > div[data-selection-index="{indice_seleccion}"]'
        )
        fila_eliminada.wait_for(state="detached", timeout=30000)
        log.info("Carpeta existente eliminada: %s", nombre_carpeta)
        return

    log.debug("No hay carpeta existente para eliminar: %s", nombre_carpeta)


def _cargar_archivos(
    pagina: Page,
    correo_usuario: str,
    tipo: Literal["archivo", "carpeta"],
    rutas: list[str],
    url_carpeta: str,
    intentos: int = 3,
) -> None:
    """Sube rutas recargando la pagina en cada intento (el timing es flaky).

    Por intento: recarga carpeta -> abre menu -> file chooser (5s).
    Sin fallback a input oculto: no sirve. Agotados los intentos
    propaga el ultimo error.
    """
    ultimo_error: PlaywrightTimeoutError | None = None
    for i in range(1, intentos + 1):
        if i > 1:
            log.debug("Recargando carpeta (intento %d)", i)
        _ir_a_carpeta(pagina, correo_usuario, url_carpeta)

        boton_subir = pagina.locator(XPATH_BOTON_CREAR_O_SUBIR)
        boton_subir.wait_for(state="visible", timeout=30000)
        boton_subir.click()

        if tipo == "archivo":
            boton_elegir = pagina.locator(XPATH_BOTON_SUBIR_ARCHIVO)
        else:
            boton_elegir = pagina.locator(XPATH_BOTON_SUBIR_CARPETA)
        boton_elegir.wait_for(state="visible", timeout=10000)
        log.debug("Menú Cargar abierto (%s)", tipo)

        try:
            with pagina.expect_file_chooser(timeout=5000) as info_selector:
                boton_elegir.click()
            info_selector.value.set_files(rutas)
            log.debug("File chooser detectado (intento %d)", i)
            return
        except PlaywrightTimeoutError as e:
            ultimo_error = e
            log.warning("Intento %d/%d sin chooser", i, intentos)
    assert ultimo_error is not None
    raise ultimo_error


def _esperar_fin_subida(pagina: Page, verbo: str) -> None:
    """Espera el toast de progreso y confirma Reemplazar si aparece.

    Sin dialogo de reemplazo es el caso normal (no habia colision): DEBUG y
    salir. Si el dialogo aparece y falla el reintento, WARNING con detalle:
    la subida ya ocurrio, propagar haria que el llamador repita todo.
    """
    aviso_progreso = pagina.get_by_role("alert").filter(has_text=verbo)
    aviso_progreso.wait_for(state="attached", timeout=10000)
    aviso_progreso.wait_for(state="detached", timeout=120000)

    boton_reemplazar = pagina.get_by_role("button", name="Reemplazar")
    try:
        boton_reemplazar.wait_for(state="attached", timeout=5000)
    except PlaywrightTimeoutError:
        log.debug("Sin dialogo de reemplazo: no habia archivos homonimos")
        return

    try:
        boton_reemplazar.click()
        log.info("Reemplazando...")
        aviso_progreso.wait_for(state="attached", timeout=5000)
        aviso_progreso.wait_for(state="detached", timeout=120000)
    except Exception as error: # El archivo ya se subio; se reporta sin abortar.  # noqa: BLE001
        log.warning("Reemplazo no confirmado: %s", error)


def _subir_archivos_a_carpeta(
    pagina: Page,
    correo_usuario: str,
    url_carpeta: str,
    rutas_archivos: list[str],
) -> None:
    """Sube una lista de archivos a la carpeta destino."""
    normalizadas = [str(Path(ruta)) for ruta in rutas_archivos]

    log.info("Subiendo %d archivo(s)", len(normalizadas))
    _cargar_archivos(pagina, correo_usuario, "archivo", normalizadas, url_carpeta)
    _esperar_fin_subida(pagina, "Cargando")
    log.info("Archivos subidos")


def _subir_carpetas_a_carpeta(
    pagina: Page,
    correo_usuario: str,
    url_carpeta: str,
    rutas_carpetas: list[str],
) -> None:
    """Elimina una carpeta homonima y sube cada carpeta desde pagina fresca."""
    normalizadas = [str(Path(ruta)) for ruta in rutas_carpetas]

    for ruta_carpeta in normalizadas:
        carpeta = Path(ruta_carpeta)
        nombre_carpeta = carpeta.name
        if not any(carpeta.iterdir()):
            log.info("Carpeta vacía; se omite: %s", nombre_carpeta)
            continue

        log.info("Subiendo carpeta: %s", nombre_carpeta)
        _ir_a_carpeta(pagina, correo_usuario, url_carpeta)
        _eliminar_carpeta_existente(pagina, nombre_carpeta)
        _cargar_archivos(pagina, correo_usuario, "carpeta", [ruta_carpeta], url_carpeta)
        _esperar_fin_subida(pagina, "Actualizando")
        log.info("Carpeta subida")
