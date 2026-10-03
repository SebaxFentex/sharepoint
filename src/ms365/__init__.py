import logging

# Receta oficial para librerias: NullHandler para no hacer ruido sin
# configuracion. Configurar handlers/niveles es trabajo del entrypoint
# (ver ms365._logging.setup_logging), nunca de la libreria.
logging.getLogger(__name__).addHandler(logging.NullHandler())
