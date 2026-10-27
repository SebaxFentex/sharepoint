class ExcepcionNoAutenticado(Exception):
    """Se lanza cuando la sesion de Microsoft ha expirado o no esta autenticada."""

    codigo_salida = 3


class ExcepcionCarpetaNoEncontrada(Exception):
    """Se lanza cuando la carpeta de SharePoint no existe (404)."""

    codigo_salida = 2
