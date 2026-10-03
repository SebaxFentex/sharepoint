"""Cliente SharePoint para cargas y descargas con Playwright."""

import logging
from contextlib import contextmanager

from playwright.sync_api import BrowserContext, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from . import _download, _upload
from ._base import browser_window_kwargs, profile_dir
from ._exceptions import NotAuthenticatedException

log = logging.getLogger(__name__)


class SharepointClient:
    """
    Cliente SharePoint con sesion persistente para subir y descargar recursos.

    Mantiene el navegador y coordina las operaciones sobre su contexto.

    Si la sesion de Microsoft no esta disponible, los metodos publicos lanzan
    NotAuthenticatedException.
    """

    def __init__(
        self,
        user_email: str,
        home_url: str,
        headless: bool = True,
        slow_mo: int = 0,
    ):
        """Inicializa el cliente y valida autenticacion al arrancar.

        El perfil de navegador dedicado siempre es
        %LOCALAPPDATA%/programas_python/ms365/perfil_navegador_playwright
        (ver ms365.sharepoint._base). No usa perfiles del navegador.

        Args:
            user_email: Correo usado para validar contexto de sesion en la UI.
            home_url: URL para validar sesion al arrancar (requerido, sin default).
            headless: Ejecuta el navegador sin interfaz grafica si es True.
            slow_mo: Retardo entre acciones de Playwright en milisegundos (debug headed).

        Raises:
            NotAuthenticatedException: si se detecta pantalla de login.
        """
        self.user_email = user_email
        target = profile_dir()
        log.info("Perfil: %s | headless=%s", target, headless)
        self._playwright = sync_playwright().start()
        self._context: BrowserContext = self._playwright.chromium.launch_persistent_context(
            user_data_dir=target,
            headless=headless,
            slow_mo=slow_mo,
            **browser_window_kwargs(headless),
        )

        self._initialize_session(home_url)

    def __enter__(self):
        """Permite usar el cliente con with."""
        return self

    def __exit__(self, *args):
        """Cierra recursos al salir del bloque with."""
        self.close()

    def close(self):
        """Cierra el navegador y libera recursos."""
        try:
            for page in self._context.pages:
                page.close()
            self._context.close()
        except Exception: # Puede estar ya cerrado; no es un error funcional para el llamador.  # noqa: S110
            pass
        log.debug("Navegador cerrado")

    def upload_files(self, files_by_folder: dict[str, list[str]]) -> None:
        """
        Sube archivos a una o varias carpetas de SharePoint.

        Args:
            files_by_folder: Diccionario donde la clave es la URL de la carpeta
                             destino en SharePoint y el valor es una lista de
                             rutas de archivos locales a subir.

        Raises:
            NotAuthenticatedException: si no hay sesion valida o contexto disponible.
        """
        log.info("Subida de archivos: %d destino(s)", len(files_by_folder))
        with self._page() as page:
            _upload.upload_files(page, self.user_email, files_by_folder)
        log.info("Subida de archivos completa")

    def upload_folders(self, folders_by_folder: dict[str, list[str]]) -> None:
        """
        Sube carpetas a una o varias carpetas destino de SharePoint.

        Antes de subir cada carpeta, elimina una carpeta existente con el
        mismo nombre. Los archivos con ese nombre se conservan.

        Raises:
            NotAuthenticatedException: si no hay sesion valida o contexto disponible.
            RuntimeError: si no se puede identificar el tipo de un elemento coincidente.
        """
        log.info("Subida de carpetas: %d destino(s)", len(folders_by_folder))
        with self._page() as page:
            _upload.upload_folders(page, self.user_email, folders_by_folder)
        log.info("Subida de carpetas completa")

    def download_folder(self, folder_url: str, destination_dir: str) -> None:
        """Descarga una carpeta SharePoint como zip y la extrae.

        Args:
            folder_url: URL de carpeta SharePoint.
            destination_dir: Carpeta local destino para extraccion.

        Raises:
            NotAuthenticatedException: si el cliente no esta disponible.
            FolderNotFoundException: si la carpeta no existe en SharePoint.
        """
        log.debug("Descarga de carpeta: %s -> %s", folder_url, destination_dir)
        with self._page() as page:
            _download.download_folder(page, folder_url, destination_dir)

    def download_single_file(self, shared_file_url: str, destination_path: str) -> None:
        """Descarga un archivo desde un vinculo compartido de SharePoint.

        Args:
            shared_file_url: URL compartida de archivo (debe incluir parametro d).
            destination_path: Ruta local de archivo o carpeta destino.

        Raises:
            NotAuthenticatedException: si el cliente no esta disponible.
            ValueError: si la URL compartida no permite construir UniqueId valido.
        """
        log.debug("Descarga de archivo compartido -> %s", destination_path)
        with self._page() as page:
            _download.download_single_file(page, shared_file_url, destination_path)

    def _initialize_session(self, home_url: str) -> None:
        """Abre SharePoint Home y valida si la sesion sigue autenticada.

        Raises:
            NotAuthenticatedException: cuando aparece la pantalla de inicio de sesion.
        """
        page = self._get_page()
        page.goto(home_url, wait_until="domcontentloaded")

        try:
            page.wait_for_function(
                "title => document.title === title",
                arg="Iniciar sesión en la cuenta",
                timeout=10000,
            )
        except PlaywrightTimeoutError:
            log.info("Sesión válida")
            return

        self.close()
        log.error("Sesión vencida")
        raise NotAuthenticatedException(
            "Sesion vencida. Ejecuta scripts/login.bat en una sesion interactiva y reintenta."
        )

    def _get_page(self) -> Page:
        """Retorna una pagina activa o crea una nueva si no existe."""
        page = self._context.pages[0] if self._context.pages else self._context.new_page()
        return page

    @contextmanager
    def _page(self):
        """Pagina temporal: unifica los 5 bloques try/new_page/finally-close."""
        try:
            page = self._context.new_page()
        except PlaywrightError:
            log.error("Contexto del navegador no disponible")
            raise NotAuthenticatedException(
                "Cliente SharePoint no disponible. Crea una nueva instancia despues de iniciar sesion."
            )
        try:
            yield page
        finally:
            page.close()
