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

## Dimensión temporal (integrante 3)

**Pregunta:** ¿cómo ha cambiado la población detenida durante el periodo
disponible?

**Indicadores:** stock del último corte, crecimiento total de la serie y
ritmo diario promedio.

**Visualizaciones:** stock por corte, variación respecto al corte
comparable anterior y cierre y crecimiento neto por año.

**Filtros:** país de prisión y situación jurídica.

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