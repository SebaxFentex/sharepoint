from ms365.sharepoint._exceptions import (
    FolderNotFoundException,
    NotAuthenticatedException,
)
from ms365.sharepoint.client import SharepointClient

# Nota: auth.login NO se re-exporta aqui a proposito. Importarlo en el
# __init__ hace que `python -m ms365.sharepoint.auth` emita RuntimeWarning
# (modulo ya en sys.modules antes de ejecutarse como __main__).
# Canonico: from ms365.sharepoint.auth import login
__all__ = [
    "FolderNotFoundException",
    "NotAuthenticatedException",
    "SharepointClient",
]
