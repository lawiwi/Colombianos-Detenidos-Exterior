# Configuracion de gunicorn para la publicacion.
#
# Los valores de abajo estan ajustados al comportamiento real de esta
# aplicacion, no a los valores por defecto de gunicorn. El motivo de
# cada ajuste esta comentado en la linea donde aparece.
#
# Se usa con:
#     gunicorn --config gunicorn.conf.py wsgi:app

import multiprocessing
import os


# ------------------------------------------------------------
# ENTRADA
# ------------------------------------------------------------

bind = os.environ.get("BIND", "0.0.0.0:" + os.environ.get("PORT", "8000"))
wsgi_app = "wsgi:app"


# ------------------------------------------------------------
# PROCESOS
# ------------------------------------------------------------
# El dataset pesa 54 MB y al normalizarlo queda en memoria un DataFrame
# de unas 256 MB. Cada worker de gunicorn es un proceso independiente, asi
# que cada uno paga esa memoria: con 4 workers serian mas de 1 GB solo en
# datos. Se sube el minimo para que el plataforma asigne bien, pero no se
# fija un numero alto a proposito.

workers = int(os.environ.get("WEB_CONCURRENCY", "2"))

# Hilos por worker: las rutas hacen trabajo de CPU (pandas y Plotly), pero
# tambien hay lecturas de disco y armado de HTML. Un solo hilo por worker
# evita que dos peticiones del mismo dataset se peleen por la CPU.
threads = int(os.environ.get("THREADS", "2"))
worker_class = "gthread"


# ------------------------------------------------------------
# TIEMPOS
# ------------------------------------------------------------
# El limite por defecto de gunicorn es de 30 segundos y aqui no alcanza:
# la primera peticion lee y normaliza el CSV completo, y las paginas de
# analisis construyen varias graficas de Plotly antes de responder. Sin
# este margen el worker muere y el navegador ve un error 502 en la primera
# visita, que es el sintoma clasico de un despliegue mal ajustado.

timeout = int(os.environ.get("WEB_TIMEOUT", "180"))
graceful_timeout = 30
keepalive = 5


# ------------------------------------------------------------
# RECARGA Y DIAGNOSTICO
# ------------------------------------------------------------

# En produccion nunca debe recargar solo: cada recarga descarta el
# dataset cacheado y obliga a releer los 54 MB.
reload = False

# Un worker que muere se levanta solo. Con la memoria que usa esta app,
# conviene que el reinicio sea rapido y visible en el log de la plataforma.
max_requests = 200
max_requests_jitter = 50

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")

# El arranque no imprime el banner para que el log de la plataforma
# muestre solo lo que importa durante la revisión.
spew = False


# ------------------------------------------------------------
# MEMORIA
# ------------------------------------------------------------
# El limite que se agota primero es el de memoria, no el de CPU.
# Estos parametros no reservan memoria: solo permiten detectar temprano
# un worker que se pasa de memoria al cargar el dataset.

preload_app = False


def post_fork(server, worker):
    """
    Comprueba, ya en el worker, que el dataset esta disponible.

    Si el CSV no viajo en la imagen, cada pagina va a fallar por igual.
    Avisar en el log de arranque es mucho mas facil de diagnosticar que
    interpretar un error 500 desde el navegador.
    """
    import os as _os

    from app import DATA_PATH

    if _os.path.exists(DATA_PATH):
        server.log.info(
            "Dataset disponible (%s MB)",
            round(_os.path.getsize(DATA_PATH) / 1_048_576, 1),
        )
    else:
        server.log.error(
            "El dataset NO esta en la imagen. Se espera en: %s", DATA_PATH
        )