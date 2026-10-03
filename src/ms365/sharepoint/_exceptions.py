class NotAuthenticatedException(Exception):
    """Se lanza cuando la sesion de Microsoft ha expirado o no esta autenticada."""


class FolderNotFoundException(Exception):
    """Se lanza cuando la carpeta de SharePoint no existe (404)."""
