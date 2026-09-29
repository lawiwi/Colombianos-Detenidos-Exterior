import os
import pandas as pd
import plotly.express as px
import unicodedata


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.path.join(
    BASE_DIR,
    "data",
    "Colombianos_detenidos_en_el_exterior.csv"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "data",
    "analisis_poblacional"
)

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# UTILIDADES
# ============================================================

def sin_acentos(texto):
    if texto is None:
        return ""
    texto = str(texto).strip().lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def cargar_dataset():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"No existe el archivo:\n{DATA_PATH}"
        )
    try:
        df = pd.read_csv(DATA_PATH, encoding="utf-8", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(DATA_PATH, encoding="latin-1", low_memory=False)
    return df


def obtener_columna(df, posibles):
    columnas = {sin_acentos(col): col for col in df.columns}
    for nombre in posibles:
        if sin_acentos(nombre) in columnas:
            return columnas[sin_acentos(nombre)]
    raise KeyError(
        "No se encontró ninguna columna compatible: "
        + ", ".join(posibles)
    )


# ============================================================
# CARGA
# ============================================================

df = cargar_dataset()

print("=" * 70)
print("ANÁLISIS DE LA DIMENSIÓN POBLACIONAL")
print("=" * 70)

print("\nArchivo:", DATA_PATH)
print("Registros:", f"{len(df):,}")
print("Columnas:", df.columns.tolist())


# ============================================================
# COLUMNAS
# ============================================================

col_cantidad = obtener_columna(df, ["CANTIDAD", "cantidad"])
col_genero   = obtener_columna(df, ["GÉNERO", "GENERO", "genero"])
col_edad     = obtener_columna(df, ["GRUPO EDAD", "GRUPO_EDAD", "grupo_edad"])
col_pais     = obtener_columna(df, ["PAIS PRISIÓN", "PAIS PRISION"])
col_delito   = obtener_columna(df, ["DELITO", "delito"])


# ============================================================
# LIMPIEZA
# ============================================================

df[col_cantidad] = pd.to_numeric(df[col_cantidad], errors="coerce")

for columna in [col_genero, col_edad, col_pais, col_delito]:
    df[columna] = df[columna].astype("string").str.strip()


# ============================================================
# INDICADORES GENERALES
# ============================================================

total_registros = len(df)
poblacion_total = df[col_cantidad].sum(min_count=1)
nulos_cantidad  = df[col_cantidad].isna().sum()
porcentaje_nulos = nulos_cantidad / total_registros * 100

print("\n" + "=" * 70)
print("INDICADORES")
print("=" * 70)
print(f"\nCantidad total de registros: {total_registros:,}")
print(f"Población representada: {poblacion_total:,.0f}")
print(f"Valores nulos en CANTIDAD: {nulos_cantidad:,}")
print(f"Porcentaje nulo en CANTIDAD: {porcentaje_nulos:.2f}%")


# ============================================================
# FUNCIÓN DE DISTRIBUCIÓN
# ============================================================

def crear_distribucion(dataframe, columna):
    resultado = (
        dataframe
        .groupby(columna, dropna=False)[col_cantidad]
        .sum()
        .reset_index()
    )
    resultado.columns = ["categoria", "cantidad"]
    resultado["categoria"] = resultado["categoria"].fillna("SIN INFORMACIÓN").astype(str)

    total = resultado["cantidad"].sum()

    resultado["porcentaje"] = (
        resultado["cantidad"] / total * 100
        if total > 0 else 0
    )

    return resultado.sort_values("cantidad", ascending=False)


# ============================================================
# DISTRIBUCIONES
# ============================================================

genero = crear_distribucion(df, col_genero)
edad   = crear_distribucion(df, col_edad)
pais   = crear_distribucion(df, col_pais)
delito = crear_distribucion(df, col_delito)


print("\n" + "=" * 70)
print("DISTRIBUCIÓN POR GÉNERO")
print("=" * 70)
print(genero.to_string(index=False))


print("\n" + "=" * 70)
print("DISTRIBUCIÓN POR GRUPO DE EDAD")
print("=" * 70)
print(edad.to_string(index=False))


print("\n" + "=" * 70)
print("TOP 10 PAÍSES")
print("=" * 70)
print(pais.head(10).to_string(index=False))


print("\n" + "=" * 70)
print("TOP 10 DELITOS")
print("=" * 70)
print(delito.head(10).to_string(index=False))


# ============================================================
# CATEGORÍAS PREDOMINANTES
# ============================================================

genero_predominante  = genero.iloc[0]["categoria"] if not genero.empty else "SIN DATOS"
porcentaje_genero    = genero.iloc[0]["porcentaje"] if not genero.empty else 0

edad_predominante    = edad.iloc[0]["categoria"] if not edad.empty else "SIN DATOS"
porcentaje_edad      = edad.iloc[0]["porcentaje"] if not edad.empty else 0

pais_predominante    = pais.iloc[0]["categoria"] if not pais.empty else "SIN DATOS"
cantidad_pais        = pais.iloc[0]["cantidad"] if not pais.empty else 0
porcentaje_pais      = pais.iloc[0]["porcentaje"] if not pais.empty else 0

delito_predominante  = delito.iloc[0]["categoria"] if not delito.empty else "SIN DATOS"
cantidad_delito      = delito.iloc[0]["cantidad"] if not delito.empty else 0
porcentaje_delito    = delito.iloc[0]["porcentaje"] if not delito.empty else 0


# ============================================================
# RESUMEN
# ============================================================

resumen = pd.DataFrame({
    "indicador": [
        "Total de registros",
        "Población representada",
        "Valores nulos en CANTIDAD",
        "Porcentaje nulo CANTIDAD",
        "Género predominante",
        "Participación género predominante",
        "Grupo de edad predominante",
        "Participación grupo edad predominante",
        "País con mayor concentración",
        "Cantidad en país predominante",
        "Participación país predominante",
        "Delito predominante",
        "Cantidad en delito predominante",
        "Participación delito predominante"
    ],
    "valor": [
        total_registros,
        poblacion_total,
        nulos_cantidad,
        porcentaje_nulos,
        genero_predominante,
        porcentaje_genero,
        edad_predominante,
        porcentaje_edad,
        pais_predominante,
        cantidad_pais,
        porcentaje_pais,
        delito_predominante,
        cantidad_delito,
        porcentaje_delito
    ]
})


# ============================================================
# EXPORTAR CSV
# ============================================================

resumen.to_csv(os.path.join(OUTPUT_DIR, "indicadores_poblacionales.csv"),
               index=False, encoding="utf-8-sig")

genero.to_csv(os.path.join(OUTPUT_DIR, "distribucion_genero.csv"),
              index=False, encoding="utf-8-sig")

edad.to_csv(os.path.join(OUTPUT_DIR, "distribucion_edad.csv"),
            index=False, encoding="utf-8-sig")

pais.to_csv(os.path.join(OUTPUT_DIR, "distribucion_pais.csv"),
            index=False, encoding="utf-8-sig")

delito.to_csv(os.path.join(OUTPUT_DIR, "distribucion_delito.csv"),
              index=False, encoding="utf-8-sig")


# ============================================================
# GRÁFICA 1 - GÉNERO
# ============================================================

fig_genero = px.bar(
    genero,
    x="categoria",
    y="cantidad",
    text="porcentaje",
    title="Distribución de la población por género",
    labels={"categoria": "Género", "cantidad": "Personas"}
)

fig_genero.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
fig_genero.update_layout(template="plotly_dark", height=500)

fig_genero.write_html(
    os.path.join(OUTPUT_DIR, "grafica_genero.html"),
    include_plotlyjs="cdn"
)


# ============================================================
# GRÁFICA 2 - EDAD
# ============================================================

edad_grafica = edad.sort_values("cantidad", ascending=True)

fig_edad = px.bar(
    edad_grafica,
    x="cantidad",
    y="categoria",
    orientation="h",
    title="Distribución de la población por grupo de edad",
    labels={"categoria": "Grupo de edad", "cantidad": "Personas"}
)

fig_edad.update_layout(template="plotly_dark", height=500)

fig_edad.write_html(
    os.path.join(OUTPUT_DIR, "grafica_edad.html"),
    include_plotlyjs=False
)


# ============================================================
# GRÁFICA 3 - DELITO (TOP 10)
# ============================================================

top_delitos = delito.head(10).sort_values("cantidad", ascending=True)

fig_delito = px.bar(
    top_delitos,
    x="cantidad",
    y="categoria",
    orientation="h",
    text="porcentaje",
    title="Top 10 delitos asociados a la detención",
    labels={"categoria": "Delito", "cantidad": "Personas"}
)

fig_delito.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
fig_delito.update_layout(template="plotly_dark", height=600)

fig_delito.write_html(
    os.path.join(OUTPUT_DIR, "grafica_delito.html"),
    include_plotlyjs=False
)


# ============================================================
# FINAL
# ============================================================

print("\n" + "=" * 70)
print("ANÁLISIS FINALIZADO")
print("=" * 70)
print("\nResultados guardados en:", OUTPUT_DIR)