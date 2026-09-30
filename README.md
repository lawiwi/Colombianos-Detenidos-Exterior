# Análisis de detenciones de colombianos en el exterior

## Ejecutar la aplicación

Desde la carpeta `Colombianos-Detenidos-Exterior`:

```powershell
python app.py
```

Abre la dirección local que indique Flask y selecciona **D4** en la navegación
superior para acceder al tablero de Análisis Relacional y Multivariado. La
dirección directa es `/dimension-4`.

La ruta utiliza el CSV local `data/Colombianos_detenidos_en_el_exterior.csv`.
El dashboard incluye filtros por país y por delito o situación jurídica,
indicadores, visualizaciones y los tres análisis de conocimiento evidente.

## Componentes

- `app.py`: aplicación Flask y lógica de la Dimensión 4.
- `templates/dim_4.html`: interfaz y contenido del tablero relacional.
- `data/Colombianos_detenidos_en_el_exterior.csv`: fuente local de datos.
