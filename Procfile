# Comando de arranque de la aplicacion web.
#
# Las plataformas que leen este archivo (Heroku, Render, Railway y varias
# mas) inician el servicio con la linea de abajo. El servidor de
# desarrollo de Flask no se usa en produccion: es monoproceso y se queda
# sin respuesta en cuanto llegan dos visitas a la vez.
#
# El puerto lo inyecta la plataforma en la variable de entorno PORT. Por
# eso el bind se deja resolver dentro de gunicorn.conf.py y no se escribe
# aqui.

web: gunicorn --config gunicorn.conf.py wsgi:app