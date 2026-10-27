import logging

logging.getLogger(__name__).addHandler(logging.NullHandler())

from sharepoint._excepciones import (
    ExcepcionCarpetaNoEncontrada,
    ExcepcionNoAutenticado,
)
from sharepoint.cliente import ClienteSharepoint

# Nota: login_manual NO se re-exporta aqui a proposito para mantener la
# superficie publica minima (cliente + excepciones). Canonico:
# from sharepoint.cliente import login_manual
__all__ = [
    "ClienteSharepoint",
    "ExcepcionCarpetaNoEncontrada",
    "ExcepcionNoAutenticado",
]
