"""Configuracion de gunicorn para el despliegue en Render.

Render publica la variable de entorno PORT y espera que el proceso
escuche en ella; de eso se encarga `bind`.

La decision de memoria es la importante. El dataset procesado ocupa
alrededor de 250 MB y los planes free y Starter de Render dan 512 MB,
asi que se usa un solo trabajador: con dos, cada uno mantendria su
propia copia del CSV y el proceso moriria por falta de memoria. Como un
trabajador solo no atenderia dos peticiones a la vez, se usan varios
hilos (clase gthread), que comparten la misma memoria.

`preload_app` carga la aplicacion, y con ella el dataset por medio de
wsgi.py, una sola vez en el proceso maestro antes de repartir el
trabajo. Los hilos heredan esa copia, de modo que el CSV se lee una vez
y no una por trabajador.

Variables (todas opcionales):

    WEB_CONCURRENCY   trabajadores. Por defecto 1.
    WEB_THREADS       hilos por trabajador. Por defecto 4.
    WEB_TIMEOUT       segundos por peticion. Por defecto 120, para que
                      la primera lectura del CSV no corte la conexion.
"""

import os


bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"

worker_class = "gthread"
workers = int(os.environ.get("WEB_CONCURRENCY", 1))
threads = int(os.environ.get("WEB_THREADS", 4))

preload_app = True

timeout = int(os.environ.get("WEB_TIMEOUT", 120))
graceful_timeout = 30
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("WEB_LOG_LEVEL", "info")
