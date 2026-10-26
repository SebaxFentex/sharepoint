import logging

logging.getLogger(__name__).addHandler(logging.NullHandler())

from sharepoint._excepciones import (
    ExcepcionCarpetaNoEncontrada,
    ExcepcionNoAutenticado,
)
from sharepoint.cliente import ClienteSharepoint

# Nota: autenticacion.iniciar_sesion NO se re-exporta aqui a proposito. Importarlo en el
# __init__ hace que `python -m sharepoint.autenticacion` emita RuntimeWarning
# (modulo ya en sys.modules antes de ejecutarse como __main__).
# Canonico: from sharepoint.autenticacion import iniciar_sesion
__all__ = [
    "ClienteSharepoint",
    "ExcepcionCarpetaNoEncontrada",
    "ExcepcionNoAutenticado",
]
