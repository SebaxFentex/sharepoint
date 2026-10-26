"""Cliente SharePoint para cargas y descargas con Playwright."""

import logging
from contextlib import contextmanager

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
    ExcepcionNoAutenticado.
    """

    def __init__(
        self,
        correo_usuario: str,
        url_inicio: str,
        sin_ventana: bool = True,
        pausa_ms: int = 0,
    ):
        """Inicializa el cliente y valida autenticacion al arrancar.

        El perfil de navegador dedicado siempre es
        %LOCALAPPDATA%/programas_python/sharepoint/perfil_navegador_playwright
        (ver sharepoint._env). No usa perfiles del navegador.

        Args:
            correo_usuario: Correo usado para validar contexto de sesion en la UI.
            url_inicio: URL para validar sesion al arrancar (requerido, sin default).
            sin_ventana: Ejecuta el navegador sin interfaz grafica si es True.
            pausa_ms: Retardo entre acciones de Playwright en milisegundos (debug headed).

        Raises:
            ExcepcionNoAutenticado: si se detecta pantalla de login.
        """
        self.correo_usuario = correo_usuario
        destino = carpeta_perfil()
        log.info("Perfil: %s | sin_ventana=%s", destino, sin_ventana)
        self._playwright = sync_playwright().start()
        self._context: BrowserContext = self._playwright.chromium.launch_persistent_context(
            user_data_dir=destino,
            headless=sin_ventana,
            slow_mo=pausa_ms,
            **parametros_ventana(sin_ventana),
        )

        self._iniciar_sesion(url_inicio)

    def __enter__(self):
        """Permite usar el cliente con with."""
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

    def _iniciar_sesion(self, url_inicio: str) -> None:
        """Abre SharePoint Home y valida si la sesion sigue autenticada.

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

        self.cerrar()
        log.error("Sesión vencida")
        raise ExcepcionNoAutenticado(
            "Sesion vencida. Ejecuta ejecutables/login.bat en una sesion interactiva y reintenta."
        )

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
