"""Punto de entrada WSGI para el servidor de produccion.

Render arranca la aplicacion con `gunicorn wsgi:app`. Este modulo
importa la app de Flask y deja el dataset ya leido y normalizado en la
cache del proceso. Como gunicorn trabaja con `preload_app = True` (ver
gunicorn.conf.py), esa carga ocurre una sola vez en el proceso maestro y
los trabajadores la heredan por copia en escritura: el CSV de 54 MB no
se duplica por trabajador y la primera visita no paga la lectura.

En desarrollo se puede seguir usando `python app.py`, que no pasa por
aqui y carga el dataset en la primera peticion.
"""

import os

from app import app, cargar_dataset_procesado


def _precalentar():
    """Lee el dataset antes de servir trafico.

    Si el archivo falta o no se puede procesar, se levanta el error: es
    preferible que el despliegue falle de entrada a que la aplicacion
    publique paginas rotas. Se puede desactivar con PRECALENTAR_DATASET=0.
    """

    if os.environ.get("PRECALENTAR_DATASET", "1") != "1":
        return

    df = cargar_dataset_procesado()
    print(f"[wsgi] dataset precalentado: {len(df):,} filas en cache")


_precalentar()


__all__ = ["app"]
