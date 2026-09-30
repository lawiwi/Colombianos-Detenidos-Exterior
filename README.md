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
wsgi.py                       Punto de entrada del servidor de producción
gunicorn.conf.py              Ajuste de gunicorn para este proyecto
Procfile                      Comando de arranque de la plataforma
runtime.txt                   Versión de Python del despliegue
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
  verificar_publicacion.py    Control de calidad del despliegue
data/
  Colombianos_detenidos_en_el_exterior.csv
```

---

## Ejecutar el proyecto localmente

Requiere Python 3.12 (la versión exacta está en `.python-version`).

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

---

## Publicar la aplicación

La publicación usa `gunicorn`, no el servidor de desarrollo de Flask: el
servidor de desarrollo es monoproceso y se queda sin respuesta en cuanto
llega una segunda visita.

### Archivos que sostienen el despliegue

| Archivo | Función |
|---|---|
| `wsgi.py` | Expone la aplicación como objeto WSGI. |
| `Procfile` | Comando de arranque: `gunicorn --config gunicorn.conf.py wsgi:app`. |
| `gunicorn.conf.py` | Workers, hilos y tiempos ajustados al peso del dataset. |
| `runtime.txt` | Fija Python 3.12.11 en la plataforma. |
| `requirements.txt` | Versiones fijadas de las seis dependencias. |

### Configuración en la plataforma

1. **Repositorio:** el mismo repositorio de GitHub del proyecto.
2. **Raíz de construcción:** la raíz del repositorio, sin subcarpeta.
3. **Comando de arranque:** vacío, si la plataforma lee el `Procfile`;
   en caso contrario, `gunicorn --config gunicorn.conf.py wsgi:app`.
4. **Plan:** un plan gratuito basta. Con los dos workers que trae
   `gunicorn.conf.py` y unos 512 MB de memoria la aplicación responde
   con normalidad.
5. **Variable de entorno:** ninguna es obligatoria. `PORT`, `WEB_CONCURRENCY`,
   `THREADS`, `WEB_TIMEOUT` y `LOG_LEVEL` tienen valores por defecto y
   se pueden fijar si la plataforma lo pide.

> Nota: el repositorio ya trae `gunicorn.conf.py` con dos workers. En
> plataformas muy pequeñas conviene bajar `WEB_CONCURRENCY=1`, porque
> cada worker mantiene su propia copia del dataset en memoria.

### Comprobar que el despliegue quedó bien

```bash
# 1. El proceso está vivo y el dataset viaja en la imagen
curl https://TU-URL.onrender.com/health
curl "https://TU-URL.onrender.com/health?carga=1"    # lee el CSV completo

# 2. Todas las páginas, los estilos y el menú
python scripts/verificar_publicacion.py https://TU-URL.onrender.com
```

Sin argumento, el mismo script levanta la aplicación con `gunicorn` y la
revisa en local:

```bash
python scripts/verificar_publicacion.py --riguroso
```

El script sale con código 0 si todo está bien y con 1 si encuentra
problemas, de modo que sirve tanto como revisión manual como dentro de un
pipeline. Revisa el código de respuesta de cada ruta, que las páginas
traigan el contenido esperado y no vengan vacías, que los cuatro archivos
de estilo se sirvan, que las rutas cortas del menú redirijan a la
dimensión correcta y que no haya texto corrupto en el HTML.

Para verificar una sola dimensión mientras las demás siguen en
construcción:

```bash
python scripts/verificar_publicacion.py --omitir /dimension-2 /dimension-4
```

### Errores de despliegue frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `502` en la primera visita | La primera petición lee y normaliza 54 MB y supera el límite de la plataforma. | El arranque ya viene con `timeout = 180`. Si persiste, subir `WEB_TIMEOUT`. |
| `500` solo en las páginas de análisis | El CSV no quedó en la imagen desplegada. | Confirmar que `data/` no está excluido por `.gitignore` y revisar `/health`. |
| Páginas sin estilos | La plataforma no está sirviendo `static/`. | Revisar que el comando de arranque no cambie el directorio de trabajo. |
| El proceso se reinicia solo | Cada worker carga su propia copia del dataset; con pocos workers no alcanza la memoria. | Bajar `WEB_CONCURRENCY=1` o subir de plan. |

---

## Dimensión temporal (integrante 3)

**Pregunta:** ¿cómo ha cambiado el comportamiento de la población durante
el periodo disponible?

**Hallazgo que condiciona el análisis.** El conjunto no registra eventos de
detención sino **cortes acumulados**: hay 64 fechas de corte distintas
para 388.148 filas, y las combinaciones de país, consulado y género de un
corte son subconjunto exacto de las del corte siguiente. Sumar
`CANTIDAD` a lo largo de los cortes cuenta cada persona tantas veces como
cortes la incluyen y produce un pico artificial en 2022. La dimensión
compara, por eso, el stock de cada corte con el del **último corte
comparable**.

**Indicadores:** stock del último corte, crecimiento total de la serie y
ritmo diario promedio.

**Visualizaciones:** stock por corte, variación respecto al corte
comparable anterior y cierre y crecimiento neto por año.

**Filtros:** país de prisión y situación jurídica.

**Conocimientos evidentes:**

1. La población detenida es estable, no creciente: +18,48 % en siete años,
   con un ritmo de 1,26 personas por día.
2. El pico de 2022 es un artefacto de republicación: +4,82 % real frente
   al +79,65 % que arroja la suma ingenua.
3. La población se fragmenta: el promedio de personas por registro baja de
   5,03 a 4,51 mientras el número de registros sube un 12,2 %.

**Limitación.** El conjunto no trae la fecha de la detención, solo la del
corte, así que no permite medir eventos de detención por mes ni
establecer estacionalidad real.

**Decisión sustentada.** Tratar la asistencia consular como un
mantenimiento estable y no como una respuesta a una emergencia, y pedir a
la fuente que publique altas y bajas en lugar de solo inventarios
acumulados.

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