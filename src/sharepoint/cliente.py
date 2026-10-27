"""Cliente SharePoint para cargas y descargas con Playwright."""

import logging
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from . import _descarga, _subida
from ._env import carpeta_perfil, parametros_ventana
from ._excepciones import ExcepcionNoAutenticado

log = logging.getLogger(__name__)


class ClienteSharepoint:
    """
    Cliente SharePoint con sesion persistente para subir y descargar recursos.

    Mantiene el navegador y coordina las operaciones sobre su contexto.

    Si la sesion de Microsoft no esta disponible, los metodos publicos lanzan
    ExcepcionNoAutenticado (codigo_salida 3).
    """

    def __init__(
        self,
        correo_usuario: str,
        url_inicio: str,
        mostrar_navegador: bool = False,
        pausa_ms: int = 0,
        permitir_login_interactivo: bool = False,
    ):
        """Inicializa el cliente (barato y total: no valida sesion).

        La validacion ocurre al entrar al `with` (ver `__enter__`).

        Args:
            correo_usuario: Correo usado para validar contexto de sesion en la UI.
            url_inicio: URL para validar sesion al arrancar (requerido, sin default).
            mostrar_navegador: Muestra el navegador si es True (debug). Default
                False: headless para scheduler.
            pausa_ms: Retardo entre acciones de Playwright en milisegundos (debug headed).
            permitir_login_interactivo: Si es True y hay ventana, ante sesion
                vencida abre el login interactivo y reintenta una vez. Default
                False: falla rapido (obligatorio para scheduler).
        """
        self.correo_usuario = correo_usuario
        self.url_inicio = url_inicio
        self.mostrar_navegador = mostrar_navegador
        self.permitir_login_interactivo = permitir_login_interactivo
        self._pausa_ms = pausa_ms
        destino = carpeta_perfil()
        log.info("Perfil: %s | mostrar_navegador=%s", destino, mostrar_navegador)
        self._playwright = sync_playwright().start()
        self._abrir_contexto(destino)

    def _abrir_contexto(self, destino: Path) -> None:
        """Abre el contexto persistente de Chromium sobre el perfil."""
        self._context: BrowserContext = self._playwright.chromium.launch_persistent_context(
            user_data_dir=destino,
            headless=not self.mostrar_navegador,
            slow_mo=self._pausa_ms,
            **parametros_ventana(self.mostrar_navegador),
        )

    def __enter__(self):
        """Valida autenticacion y entrega el cliente listo para operar.

        Raises:
            ExcepcionNoAutenticado: si se detecta pantalla de login y no
                procede el re-login interactivo.
        """
        self._iniciar_sesion(self.url_inicio)
        return self

    def __exit__(self, *args):
        """Cierra recursos al salir del bloque with."""
        self.cerrar()

    def cerrar(self):
        """Cierra el navegador y libera recursos."""
        try:
            for pagina in self._context.pages:
                pagina.close()
            self._context.close()
        except Exception: # Puede estar ya cerrado; no es un error funcional para el llamador.  # noqa: S110
            pass
        log.debug("Navegador cerrado")

    def subir_archivos(self, archivos_por_carpeta: dict[str, list[str]]) -> None:
        """
        Sube archivos a una o varias carpetas de SharePoint.

        Args:
            archivos_por_carpeta: Diccionario donde la clave es la URL de la carpeta
                             destino en SharePoint y el valor es una lista de
                             rutas de archivos locales a subir.

        Raises:
            ExcepcionNoAutenticado: si no hay sesion valida o contexto disponible.
        """
        log.info("Subida de archivos: %d destino(s)", len(archivos_por_carpeta))
        with self._pagina() as pagina:
            _subida.subir_archivos(pagina, self.correo_usuario, archivos_por_carpeta)
        log.info("Subida de archivos completa")

    def subir_carpetas(self, carpetas_por_carpeta: dict[str, list[str]]) -> None:
        """
        Sube carpetas a una o varias carpetas destino de SharePoint.

        Antes de subir cada carpeta, elimina una carpeta existente con el
        mismo nombre. Los archivos con ese nombre se conservan.

        Raises:
            ExcepcionNoAutenticado: si no hay sesion valida o contexto disponible.
            RuntimeError: si no se puede identificar el tipo de un elemento coincidente.
        """
        log.info("Subida de carpetas: %d destino(s)", len(carpetas_por_carpeta))
        with self._pagina() as pagina:
            _subida.subir_carpetas(pagina, self.correo_usuario, carpetas_por_carpeta)
        log.info("Subida de carpetas completa")

    def descargar_carpeta(self, url_carpeta: str, carpeta_destino: str) -> None:
        """Descarga una carpeta SharePoint como zip y la extrae.

        Args:
            url_carpeta: URL de carpeta SharePoint.
            carpeta_destino: Carpeta local destino para extraccion.

        Raises:
            ExcepcionNoAutenticado: si el cliente no esta disponible.
            ExcepcionCarpetaNoEncontrada: si la carpeta no existe en SharePoint.
        """
        log.debug("Descarga de carpeta: %s -> %s", url_carpeta, carpeta_destino)
        with self._pagina() as pagina:
            _descarga.descargar_carpeta(pagina, url_carpeta, carpeta_destino)

    def descargar_archivo_compartido(self, url_archivo_compartido: str, ruta_destino: str) -> None:
        """Descarga un archivo desde un vinculo compartido de SharePoint.

        Args:
            url_archivo_compartido: URL compartida de archivo (debe incluir parametro d).
            ruta_destino: Ruta local de archivo o carpeta destino.

        Raises:
            ExcepcionNoAutenticado: si el cliente no esta disponible.
            ValueError: si la URL compartida no permite construir UniqueId valido.
        """
        log.debug("Descarga de archivo compartido -> %s", ruta_destino)
        with self._pagina() as pagina:
            _descarga.descargar_archivo_compartido(pagina, url_archivo_compartido, ruta_destino)

    def _iniciar_sesion(self, url_inicio: str, reintento: bool = False) -> None:
        """Abre SharePoint Home y valida si la sesion sigue autenticada.

        Con ventana y `permitir_login_interactivo`, ante sesion vencida abre
        el login manual una sola vez y revalida. En cualquier otro caso
        cierra y lanza ExcepcionNoAutenticado.

        Raises:
            ExcepcionNoAutenticado: cuando aparece la pantalla de inicio de sesion.
        """
        pagina = self._obtener_pagina()
        pagina.goto(url_inicio, wait_until="domcontentloaded")

        try:
            pagina.wait_for_function(
                "title => document.title === title",
                arg="Iniciar sesión en la cuenta",
                timeout=10000,
            )
        except PlaywrightTimeoutError:
            log.info("Sesión válida")
            return

        if self.mostrar_navegador and self.permitir_login_interactivo and not reintento:
            log.info("Sesión vencida: abriendo login interactivo")
            self._login_interactivo(url_inicio)
            self._iniciar_sesion(url_inicio, reintento=True)
            return

        self.cerrar()
        log.error("Sesión vencida")
        raise ExcepcionNoAutenticado(
            "Sesion vencida. Inicia sesion con `python -m sharepoint <URL>` "
            "o define SHAREPOINT_URL_INICIO en el .env, en una sesion interactiva, "
            "y reintenta."
        )

    def _login_interactivo(self, url_inicio: str) -> None:
        """Abre una pestana en el propio contexto para login manual con MFA.

        No cierra ni reabre el navegador: la sesion queda guardada en el
        perfil y el mismo contexto la ve de inmediato.
        """
        pagina = self._context.new_page()
        pagina.goto(url_inicio, wait_until="domcontentloaded")
        print("Inicia sesion con tu usuario + MFA en el navegador.")
        input("Cuando veas el sitio, pulsa Enter aqui... ")
        pagina.close()

    def _obtener_pagina(self) -> Page:
        """Retorna una pagina activa o crea una nueva si no existe."""
        pagina = self._context.pages[0] if self._context.pages else self._context.new_page()
        return pagina

    @contextmanager
    def _pagina(self):
        """Pagina temporal: unifica los 5 bloques try/new_page/finally-close."""
        try:
            pagina = self._context.new_page()
        except PlaywrightError:
            log.error("Contexto del navegador no disponible")
            raise ExcepcionNoAutenticado(
                "Cliente SharePoint no disponible. Crea una nueva instancia despues de iniciar sesion."
            )
        try:
            yield pagina
        finally:
            pagina.close()


def login_manual(url_inicio: str) -> Path:
    """Login interactivo standalone (sin cliente): contexto temporal propio.

    Usado por `python -m sharepoint` y `login.bat`. Como no hay cliente
    corriendo, no hay conflicto de lock con el perfil.

    Args:
        url_inicio: Pagina a abrir para autenticarse (requerido, sin default).

    Returns:
        Ruta del perfil utilizado.
    """
    destino = carpeta_perfil()
    log.info("Abriendo perfil para login: %s", destino)
    with sync_playwright() as p:
        contexto = p.chromium.launch_persistent_context(
            user_data_dir=str(destino),
            headless=False,
            **parametros_ventana(True),
        )
        contexto.new_page().goto(url_inicio, wait_until="domcontentloaded")
        print("Inicia sesion con tu usuario + MFA en el navegador.")
        input("Cuando veas el sitio, pulsa Enter aqui... ")
        contexto.close()
    log.info("Sesion guardada en: %s", destino)
    return destino
