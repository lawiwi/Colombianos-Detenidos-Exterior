# Colombianos detenidos en el exterior

Análisis exploratorio de datos de la población de ciudadanos colombianos
detenidos en el exterior, con el propósito de identificar conocimientos
evidentes a partir de indicadores, comparaciones y visualizaciones.

- **Población estudiada:** ciudadanos colombianos detenidos en el
  exterior, según el registro del Ministerio de Relaciones Exteriores.
- **Entidad que publica los datos:** Ministerio de Relaciones Exteriores.
- **Conjunto de datos:** Portal Nacional de Datos Abiertos Colombia,
  identificador `e97j-vuf7`.
- **Aplicación:** Flask + Plotly, cuatro dimensiones de análisis.

---

## Estructura del repositorio

```
app.py                        Rutas de Flask y contexto de las plantillas
wsgi.py                       Entrada de producción para gunicorn
gunicorn.conf.py              Ajustes del servidor de producción
render.yaml                   Blueprint de despliegue en Render
.python-version               Versión de Python que usa Render
requirements.txt              Dependencias fijadas
src/
  analisis_poblacional.py     Motor de cálculo de la dimensión poblacional
  analisis_temporal.py        Motor de cálculo de la dimensión temporal
templates/
  base.html                   Menú y estructura común
  index.html                  Página de inicio
  dim_1.html ... dim_4.html   Tablero de cada dimensión
  analisis_poblacional.html   Análisis completo de la dimensión poblacional
  analisis_temporal.html      Análisis completo de la dimensión temporal
static/css/                   Hojas de estilo por tipo de página
scripts/
  verificar_publicacion.py    Revisa que cada ruta y sus recursos respondan
data/
  Colombianos_detenidos_en_el_exterior.csv
```

---

## Ejecutar el proyecto localmente

Requiere Python 3.12 o superior (las dependencias piden 3.11 o más).

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

La aplicación queda en <http://127.0.0.1:5000>.

La primera visita a una dimensión tarda alrededor de un segundo: es el
momento en que se lee y normaliza el CSV de 54 MB. A partir de ahí el
dataset queda en memoria y las páginas responden en milisegundos.

### Generar los resultados del módulo temporal

El motor de cálculo también corre sin la aplicación web y deja sus
salidas en `data/analisis_temporal/`:

```bash
python src/analisis_temporal.py
```

### Revisar que todo responda

Con el servidor levantado, el verificador recorre las páginas, los
estilos y el menú, y avisa si alguna quedó vacía o con texto corrupto:

```bash
python scripts/verificar_publicacion.py
```

Sin argumento revisa <http://127.0.0.1:5000>. Acepta otra base como
argumento y `--omitir /dimension-2 /dimension-4` para revisar una sola
dimensión mientras las demás están en construcción.

---

## Desplegar en Render

El repositorio trae un **Blueprint** (`render.yaml`) para que el
despliegue quede escrito y no dependa de acordarse de cada comando.

1. En [Render](https://dashboard.render.com) entra a *New > Blueprint* y
   conecta este repositorio.
2. Render detecta `render.yaml` y muestra el servicio. Confirma y espera
   el primer despliegue.
3. La aplicación queda en una URL `https://<nombre>.onrender.com`.

Si prefieres crearlo a mano con *New > Web Service*, usa estos valores:

| Ajuste | Valor |
|---|---|
| Language | `Python 3` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn wsgi:app -c gunicorn.conf.py` |
| Health Check Path | `/health` |

### Cómo funciona el arranque

- `wsgi.py` lee y normaliza el CSV **antes** de recibir tráfico, así que
  la primera visita ya encuentra el dataset listo.
- `gunicorn.conf.py` escucha en la variable `PORT` que publica Render y
  carga la aplicación una sola vez (`preload_app`), de modo que el CSV
  vive en el proceso maestro y los trabajadores lo comparten.
- `.python-version` fija la versión de Python; Render la lee en el build.

### Sobre los recursos

El DataFrame procesado ocupa alrededor de 250 MB. El plan **free** de
Render da 512 MB y 0,1 CPU, por eso la configuración usa **un solo
trabajador con hilos** en lugar de varios procesos: dos procesos
tendrían cada uno su copia del CSV y agotarían la memoria. Si subes a un
plan con más memoria, aumenta el número de trabajadores añadiendo las
variables `WEB_CONCURRENCY` y `WEB_THREADS` en el panel de Render, sin
tocar código.

En el plan free el servicio se duerme tras un rato sin visitas; la
siguiente petición lo despierta y tarda unos segundos en volver, lo que
tarda en releer el CSV.

> El conjunto de datos (54 MB) debe viajar en el repositorio. Ya está
> versionado en `data/`; si alguna vez se ignora en `.gitignore`, Render
> servirá páginas vacías y `/health` lo reportará.

---

## Dimensión temporal (integrante 3)

**Pregunta:** ¿cómo ha cambiado la población detenida durante el periodo
disponible?

**Indicadores:** stock del último corte, crecimiento total de la serie y
ritmo diario promedio.

**Visualizaciones:** stock por corte, variación respecto al corte
comparable anterior y cierre y crecimiento neto por año.

**Filtros:** rango de años del corte. La dimensión temporal no filtra
por variables poblacionales (país, situación jurídica); su filtro es su
propia variable de tiempo.

**Conocimientos evidentes:**

1. La población detenida es estable, no creciente: +18,48 % en siete años,
   con un ritmo de 1,26 personas por día.
2. El calendario de publicación es irregular: hay años con un solo corte
   y otros con doce, con huecos de hasta 184 días. No hay un corte por
   mes, así que la comparación válida es por día y no por mes.
3. La población se fragmenta: el promedio de personas por registro baja de
   5,03 a 4,51 mientras el número de registros sube un 12,2 %.

**Limitación.** El conjunto no trae la fecha de la detención, solo la del
corte, así que no permite medir eventos de detención por mes ni
establecer estacionalidad real.

**Decisión sustentada.** Tratar la asistencia consular como un
mantenimiento estable y no como una respuesta a una emergencia, y pedir a
la fuente que publique un calendario de cortes regular y una serie de
altas y bajas en lugar de solo inventarios acumulados.

---

## Cómo se colaboró en GitHub

Cada integrante trabajó en su rama y abrió un pull request a `main`:

| Rama | Contenido |
|---|---|
| `feature/dimension-poblacional` | Dimensión poblacional y estructura inicial |
| `feature/dimension-territorial` | Dimensión territorial |
| `feature/dimension-temporal` | Dimensión temporal |
| `feature/dimension-multivariada` | Dimensión relacional y multivariada |

El integrante 1 revisa y fusiona cada pull request.