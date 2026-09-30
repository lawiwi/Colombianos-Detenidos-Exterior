"""
Verificacion de la aplicacion ya publicada.

Este script es el control de calidad del despliegue. Antes de dar por
terminada la publicacion hay que confirmar, contra la URL real y no solo
en local, que cada pagina responde, que el conjunto de datos viaja en la
imagen y que los recursos estaticos se sirven. Un despliegue puede
arrancar sin error y aun asi servir paginas en blanco si una plantilla
falta o si el CSV no subio con el codigo.

Uso:

    python scripts/verificar_publicacion.py
    python scripts/verificar_publicacion.py https://mi-app.onrender.com
    python scripts/verificar_publicacion.py --riguroso

Sin argumentos levanta la aplicacion en local y la revisa, de modo que
sirve tambien como prueba antes de publicar. Con una URL como argumento
revisa la version desplegada, que es la que se debe entregar al equipo.

Salida: 0 si todo esta bien, 1 si hay fallos. Sirve para encadenarlo en
un pipeline o para dejar constancia del resultado en la bitácora.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request


# ============================================================
# RUTAS QUE DEBEN FUNCIONAR
# ============================================================
# Cada entrada es (ruta, textos que tienen que aparecer en el HTML).
# Los marcadores no son decorativos: son la forma barata de detectar que
# una pagina responde con el HTTP 200 pero vino vacia o con la plantilla
# equivocada, que es el fallo mas comun al publicar.

RUTAS = [
    ("/", [
        "SISTEMA INICIALIZADO", "INICIAR ETAPA 1",
    ]),

    ("/dimension-poblacional", [
        "DIMENSIÓN POBLACIONAL", "PAÍS DE PRISIÓN",
        "POBLACIÓN TOTAL", "GÉNERO PREDOMINANTE",
        "DISTRIBUCIÓN POR GÉNERO", "CONCLUSIONES",
    ]),

    ("/analisis-poblacional", [
        "COMPOSICIÓN Y DISTRIBUCIÓN POBLACIONAL",
        "METODOLOGÍA", "CONOCIMIENTOS EVIDENTES",
    ]),

    ("/dimension-temporal", [
        "DIMENSIÓN TEMPORAL", "STOCK EN EL ÚLTIMO CORTE",
        "RITMO DIARIO PROMEDIO", "PAÍS DE PRISIÓN",
        "SITUACIÓN JURÍDICA", "APLICAR",
        "INTERPRETACIÓN", "CONCLUSIONES",
    ]),

    ("/analisis-temporal", [
        "METODOLOGÍA", "SERIE DE CORTES",
        "LECTURA COMPARADA POR AÑO", "CONOCIMIENTOS EVIDENTES",
        "VARIACIÓN POR MES DEL CALENDARIO",
        "LIMITACIÓN Y DECISIÓN SUSTENTADA",
    ]),

    ("/dimension-2", []),
    ("/dimension-4", []),
]

# Rutas de recursos estaticos. Si el proveedor no sirve /static, las
# paginas se ven sin estilos aunque devuelvan 200.
ESTATICOS = [
    "/static/css/style_base.css",
    "/static/css/style_home.css",
    "/static/css/style_dashboards.css",
    "/static/css/style_analysis.css",
]

# Un pagina con menos de este tamano en bytes se considera vacia.
TAMANO_MINIMO = 1_000


# ============================================================
# COMPROBACIONES
# ============================================================

class SinRedireccion(urllib.request.HTTPRedirectHandler):
    """Deja pasar el 302 como respuesta, en vez de seguirlo."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def pedir(url, tiempo_maximo=120):
    """
    Hace un GET y devuelve (codigo, cuerpo, segundos).

    No se usa requests porque no esta en requirements.txt: la
    verificacion tiene que poder correr en el mismo entorno de la
    aplicacion, sin instalar nada adicional.
    """
    # Las redirecciones no se siguen: el menu se sirve con
    # redirect() y hay que comprobar el 302, no la pagina de destino.
    # El manager de urllib sigue por defecto, asi que se abre con su
    # contexto y se le pasa uno que no reintenta.
    peticion = urllib.request.Request(url, headers={
        "User-Agent": "verificador-publicacion/1.0",
    })

    opener = urllib.request.build_opener(SinRedireccion)

    inicio = time.perf_counter()

    try:
        with opener.open(peticion, timeout=tiempo_maximo) as r:
            cuerpo = r.read().decode("utf-8", errors="replace")
            codigo = r.status
    except urllib.error.HTTPError as error:
        cuerpo = error.read().decode("utf-8", errors="replace")
        codigo = error.code
    except Exception as error:
        return None, f"{type(error).__name__}: {error}", time.perf_counter() - inicio

    return codigo, cuerpo, time.perf_counter() - inicio


def verificar_health(base):
    """
    Comprueba /health y, en modo riguroso, tambien la carga real del
    dataset. El endpoint devuelve 503 cuando el CSV no esta en la
    imagen, que es el fallo que mas se repite al publicar.
    """
    codigo, cuerpo, segundos = pedir(base + "/health?carga=1")

    if codigo != 200:
        return False, f"/health?carga=1 respondio {codigo}: {cuerpo[:160]}"

    try:
        estado = json.loads(cuerpo)
    except json.JSONDecodeError:
        return False, "/health no devolvio JSON"

    if estado.get("servicio") != "ok":
        return False, f"/health reporta: {estado.get('error', 'sin detalle')}"

    dataset = estado.get("dataset", {})

    if not dataset.get("presente"):
        return False, "el dataset no esta en la imagen desplegada"

    if dataset.get("registros_csv", 0) < 500:
        return False, (
            f"el dataset trae solo {dataset.get('registros_csv')} registros"
        )

    return True, (
        f"dataset OK: {dataset['registros_csv']:,} registros, "
        f"{dataset.get('cortes', '?')} cortes, "
        f"{dataset.get('bytes', 0) / 1_048_576:.1f} MB, {segundos:.2f}s"
    )


def verificar_paginas(base, rutas):
    """Recorre las rutas y devuelve la lista de fallos."""
    fallos = []

    for ruta, marcadores in rutas:
        codigo, cuerpo, segundos = pedir(base + ruta)

        if codigo is None:
            fallos.append(f"{ruta}: no respondio ({cuerpo})")
            continue

        if codigo >= 400:
            fallos.append(f"{ruta}: HTTP {codigo}")
            continue

        if len(cuerpo) < TAMANO_MINIMO:
            fallos.append(
                f"{ruta}: responded {codigo} pero con {len(cuerpo)} bytes "
                f"(pagina vacia?)"
            )
            continue

        faltantes = [m for m in marcadores if m not in cuerpo]

        if faltantes:
            fallos.append(
                f"{ruta}: HTTP {codigo} pero sin el contenido esperado "
                f"({', '.join(faltantes)})"
            )
            continue

        print(f"    {ruta:<28} {codigo}  {len(cuerpo):>9,} B  {segundos:5.2f}s")

    return fallos


def verificar_estaticos(base, estaticos):
    """Los estilos ausentes hacen que las paginas se vean sin formato."""
    fallos = []

    for ruta in estaticos:
        codigo, cuerpo, _ = pedir(base + ruta)

        if codigo != 200:
            fallos.append(f"{ruta}: HTTP {codigo}")
            continue

        if not cuerpo.strip():
            fallos.append(f"{ruta}: archivo vacio")
            continue

        print(f"    {ruta:<28} {codigo}  {len(cuerpo):>9,} B")

    return fallos


def verificar_redirecciones(base):
    """Las rutas cortas del menú deben llevar a la dimensión correcta."""
    fallos = []

    destinos = {
        "/dimension-1": "/dimension-poblacional",
        "/dimension-3": "/dimension-temporal",
    }

    for ruta, esperado in destinos.items():
        codigo, cuerpo, _ = pedir(base + ruta)

        if codigo not in (301, 302, 307, 308):
            fallos.append(
                f"{ruta}: HTTP {codigo}, se esperaba una redirección"
            )
            continue

        if f"url={esperado}" not in cuerpo and f'href="{esperado}"' not in cuerpo:
            fallos.append(f"{ruta}: no lleva a {esperado}")
            continue

        print(f"    {ruta:<28} {codigo}  -> {esperado}")

    return fallos


def verificar_textos_sospechosos(base, rutas):
    """
    Busca los rastros de un problema que ya apareció en este proyecto:
    texto corrupto por una traducción automática, con palabras de otros
    idiomas incrustadas en el HTML final.

    Es una comprobación barata que se repite en cada entrega y deja la
    publicación con texto basura si alguien vuelve a exportar las
    plantillas por la vía equivocada.
    """
    patrones = [
        r"[\u4e00-\u9fff]",          # caracteres chinos
        r"\u3002|\uff0c",           # puntuación de ancho completo
        r"\boverallocar\b",
        r"\bchinese_language\b",
        r"\bEdinburghInternas\b",
        r"\bseaotal\b",
        r"\bobtainable\b",
        r"\brepublished\b",
    ]

    fallos = []

    for ruta, _ in rutas:
        codigo, cuerpo, _ = pedir(base + ruta)

        if codigo is None or codigo >= 400:
            continue

        encontrados = [
            p for p in patrones if re.search(p, cuerpo)
        ]

        if encontrados:
            fallos.append(
                f"{ruta}: texto corrupto en la pagina ({encontrados[0]})"
            )

    return fallos


# ============================================================
# MODO LOCAL
# ============================================================

def levantar_local():
    """
    Levanta la aplicacion con el mismo servidor de produccion y la
    devuelve en ejecucion. Se usa gunicorn para que la verificacion en
    local mida lo mismo que va a medir en la plataforma publicada.
    """
    import subprocess
    import threading

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    puerto = 5099

    proceso = subprocess.Popen(
        [sys.executable, "-m", "gunicorn",
         "--config", "gunicorn.conf.py",
         "--bind", f"127.0.0.1:{puerto}",
         "wsgi:app"],
        cwd=raiz,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    base = f"http://127.0.0.1:{puerto}"

    for _ in range(60):
        if proceso.poll() is not None:
            raise RuntimeError("gunicorn se detuvo al arrancar")

        codigo, _, _ = pedir(base + "/health", tiempo_maximo=5)

        if codigo == 200:
            return proceso, base

        time.sleep(1)

    proceso.terminate()
    raise RuntimeError("gunicorn no respondio en 60 segundos")


# ============================================================
# PROGRAMA
# ============================================================

def main():
    analizador = argparse.ArgumentParser(
        description="Verifica la aplicacion antes o despues de publicarla."
    )
    analizador.add_argument(
        "url",
        nargs="?",
        default=None,
        help="URL publicada. Sin argumento, se verifica en local.",
    )
    analizador.add_argument(
        "--riguroso",
        action="store_true",
        help="Incluye /health?carga=1, que lee el dataset completo.",
    )
    analizador.add_argument(
        "--omitir",
        nargs="*",
        default=[],
        metavar="RUTA",
        help=(
            "Rutas que no se revisan. Permite verificar una dimensión "
            "aislada mientras las demás siguen en construcción, por "
            " ejemplo: --omitir /dimension-2 /dimension-4"
        ),
    )
    argumentos = analizador.parse_args()

    omitidas = set(argumentos.omitir)
    rutas = [r for r in RUTAS if r[0] not in omitidas]
    estaticos = [r for r in ESTATICOS if r not in omitidas]

    if omitidas:
        print(f"Rutas omitidas a pedido: {', '.join(sorted(omitidas))}\n")

    if argumentos.url:
        base = argumentos.url.rstrip("/")
        proceso = None
        print(f"Verificando la version publicada en {base}\n")
    else:
        proceso, base = levantar_local()
        print(f"Verificando en local, con gunicorn, en {base}\n")

    fallos = []

    try:
        print("  Salud del servicio")
        if argumentos.riguroso or argumentos.url:
            ok, detalle = verificar_health(base)
            print(f"    {'OK  ' if ok else 'FALLA'}  {detalle}")
            if not ok:
                fallos.append(f"/health: {detalle}")
        else:
            codigo, cuerpo, _ = pedir(base + "/health")
            ok = codigo == 200
            print(f"    {'OK  ' if ok else 'FALLA'}  HTTP {codigo}")
            if not ok:
                fallos.append(f"/health: HTTP {codigo}")

        print("\n  Paginas")
        fallos += verificar_paginas(base, rutas)

        print("\n  Recursos estaticos")
        fallos += verificar_estaticos(base, estaticos)

        print("\n  Redirecciones del menu")
        fallos += verificar_redirecciones(base)

        print("\n  Integridad del texto")
        fallos += verificar_textos_sospechosos(base, rutas)

    finally:
        if proceso is not None:
            proceso.terminate()
            proceso.wait(timeout=15)

    print()
    print("=" * 62)

    if fallos:
        print(f"RESULTADO: {len(fallos)} problema(s) encontrado(s)\n")
        for fallo in fallos:
            print(f"  - {fallo}")
        print("\nLa publicacion no debe darse por terminada hasta "
              "que esta lista salga vacia.")
        return 1

    print("RESULTADO: todo correcto")
    print(f"Publicacion verificada en {base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())