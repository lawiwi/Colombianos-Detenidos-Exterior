"""
Punto de entrada WSGI para la publicacion.

Los servidores de produccion no ejecutan `python app.py`: cargan este
modulo e invocan el objeto `app`. El servidor de desarrollo de Flask
sigue siendo `app.run()`, porque el bloque `__main__` de app.py no se
dispara al importar.

Se expone tambien `application`, que es el nombre que algunos
proveedores (PythonAnywhere, entre otros) buscan por defecto.

    gunicorn wsgi:app
    gunicorn --config gunicorn.conf.py wsgi:app
"""

from app import app as application

# Los dos nombres apuntan al mismo objeto. `app` es el que usa el
# Procfile del repositorio; `application` cubre los proveedores que lo
# buscan con ese nombre.
app = application


if __name__ == "__main__":
    # Solo para probar este archivo de forma aislada. El arranque real
    # en local es `python app.py`.
    application.run(host="0.0.0.0", port=5000, debug=True)