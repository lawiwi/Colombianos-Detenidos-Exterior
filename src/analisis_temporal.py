"""
Motor de calculo de la dimension temporal.

Hallazgo que condiciona todo el analisis
----------------------------------------
El conjunto de datos no registra eventos de detencion, sino CORTES
ACUMULADOS de la poblacion detenida en el exterior. Cada valor distinto
de FECHA PUBLICACION es una fecha de corte, y la suma de CANTIDAD de esa
fecha describe el stock de detenidos vigente en ese momento, no las
detenciones ocurridas durante ese mes.

Hay 64 fechas de corte distintas para 388.148 filas, y las combinaciones
de PAIS PRISION, CONSULADO y GENERO de un corte son subconjunto exacto
de las del corte siguiente. Eso confirma que cada corte reitera todo lo
publicado antes y le anade lo nuevo.

Consecuencia metodologica
-------------------------
Sumar CANTIDAD a lo largo de todos los cortes cuenta una misma persona
tantas veces como cortes la incluyen, y produce un pico artificial en
2022 que no corresponde a un aumento real de detenidos. Para estudiar la
evolucion hay que comparar el stock de cada corte con el del ultimo corte
comparable, nunca acumular.

Este modulo concentra esa logica y la expone como funciones puras sobre
un DataFrame, de manera que sirvan tanto a la ruta de Flask como a la
ejecucion directa desde la linea de comandos.
"""

import os
import unicodedata

import pandas as pd


# ============================================================
# CONFIGURACION
# ============================================================

# Dos niveles arriba porque este archivo vive en src/. Resolver la raiz
# desde aqui es lo que evita que el modulo busque el CSV en src/data/.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RUTA_DATOS = os.path.join(
    BASE_DIR, "data", "Colombianos_detenidos_en_el_exterior.csv"
)

RUTA_SALIDA = os.path.join(BASE_DIR, "data", "analisis_temporal")

# Solo se cargan las columnas que el analisis temporal necesita. El
# archivo tiene 12 columnas y 54 MB; leerlo completo consume cerca de
# cinco veces mas memoria sin aportar nada a esta dimension.
COLUMNAS_MINIMAS = ["FECHA PUBLICACIÓN", "CANTIDAD"]

COLUMNAS_OPCIONALES = ["PAIS PRISIÓN", "GÉNERO", "GRUPO EDAD", "DELITO",
                       "SITUACIÓN JURÍDICA"]

# Una repoblacion es un corte cuyo total supera en mas de 50 % el del
# ultimo corte comparable. El mayor aumento normal de la serie es de
# 4,4 % (2019-07-04) y el menor de los saltos detectados es de 99 %,
# de modo que el umbral separa ambos casos sin ambiguedad.
UMBRAL_REPOBLACION = 1.5


# ============================================================
# UTILIDADES
# ============================================================

def sin_acentos(texto):
    """Devuelve el texto en minusculas y sin diacriticos."""
    if texto is None:
        return ""
    texto = str(texto).strip().lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def ubicar_columna(df, posibles):
    """Devuelve el nombre real de la columna, o None si no existe."""
    disponibles = {sin_acentos(col): col for col in df.columns}
    for nombre in posibles:
        clave = sin_acentos(nombre)
        if clave in disponibles:
            return disponibles[clave]
    return None


# ============================================================
# CARGA
# ============================================================

def cargar_datos(solo_minimas=True):
    """
    Lee el CSV de detenidos.

    Con solo_minimas=True trae unicamente FECHA PUBLICACION y CANTIDAD,
    que es lo que exige la dimension temporal.
    """
    if not os.path.exists(RUTA_DATOS):
        raise FileNotFoundError("No se encontro el dataset en: " + RUTA_DATOS)

    columnas = COLUMNAS_MINIMAS if solo_minimas else None

    try:
        return pd.read_csv(
            RUTA_DATOS,
            encoding="utf-8",
            low_memory=False,
            usecols=columnas,
        )
    except UnicodeDecodeError:
        return pd.read_csv(
            RUTA_DATOS,
            encoding="latin-1",
            low_memory=False,
            usecols=columnas,
        )


# ============================================================
# SERIE DE CORTES
# ============================================================

def serie_de_cortes(df):
    """
    Convierte el DataFrame en la serie de cortes publicados.

    Devuelve una fila por fecha de corte con el numero de registros y el
    stock de personas, en orden cronologico.
    """
    col_fecha = ubicar_columna(df, ["FECHA PUBLICACIÓN", "FECHA PUBLICACION"])
    col_cantidad = ubicar_columna(df, ["CANTIDAD", "cantidad"])

    if col_fecha is None:
        raise KeyError("El conjunto de datos no trae columna FECHA PUBLICACION")
    if col_cantidad is None:
        raise KeyError("El conjunto de datos no trae columna CANTIDAD")

    trabajo = pd.DataFrame({
        "FECHA": pd.to_datetime(df[col_fecha], errors="coerce"),
        "CANTIDAD": pd.to_numeric(df[col_cantidad], errors="coerce").fillna(0),
    }).dropna(subset=["FECHA"])

    serie = (
        trabajo.groupby("FECHA", as_index=False)
        .agg(registros=("CANTIDAD", "size"), stock=("CANTIDAD", "sum"))
        .sort_values("FECHA")
        .reset_index(drop=True)
    )

    serie["ANIO"] = serie["FECHA"].dt.year
    serie["MES"] = serie["FECHA"].dt.month
    serie["TRIMESTRE"] = serie["FECHA"].dt.quarter
    serie["personas_por_registro"] = (
        serie["stock"] / serie["registros"].replace(0, pd.NA)
    ).round(2)

    return serie


def _columna_referencia(serie):
    """
    Stock del ultimo corte comparable anterior a cada fila.

    Se saltan las repoblaciones como punto de referencia: comparar
    marzo de 2022 contra la repoblacion de enero de 2022 daria una
    caida artificial de 134.125 personas. Tomando como referencia
    septiembre de 2021, el ultimo corte comparable, la variacion real
    de marzo es de +322 personas.
    """
    sin_repoblacion = serie["stock"].where(~serie["es_repoblacion"])
    return sin_repoblacion.ffill().shift(1)


def medir_evolucion(serie):
    """
    Anade a la serie las variaciones entre cortes comparables.

    columnas anadidas:
        es_repoblacion     Corte con salto masivo, no comparable.
        fecha_referencia   Fecha del corte comparable de referencia.
        variacion_neta     Personas de mas o menos respecto a la
                          referencia.
        variacion_pct      Esa misma variacion en porcentaje.
        dias              Dias transcurridos desde la referencia.
        variacion_diaria   Personas por dia, que neutraliza el hecho de
                          que algunos cortes llegan a dos o tres meses
                          del anterior.
    """
    serie = serie.copy()
    serie["es_repoblacion"] = serie["stock"] > (
        serie["stock"].shift(1) * UMBRAL_REPOBLACION
    )

    serie["stock_referencia"] = _columna_referencia(serie)
    serie["fecha_referencia"] = serie["FECHA"].where(
        ~serie["es_repoblacion"]
    ).ffill().shift(1)

    comparable = ~serie["es_repoblacion"] & serie["stock_referencia"].notna()

    serie["variacion_neta"] = serie["stock"] - serie["stock_referencia"]
    serie.loc[~comparable, "variacion_neta"] = pd.NA

    serie["variacion_pct"] = (
        serie["variacion_neta"] / serie["stock_referencia"] * 100
    ).round(4)

    serie["dias"] = (serie["FECHA"] - serie["fecha_referencia"]).dt.days
    serie["variacion_diaria"] = (
        serie["variacion_neta"] / serie["dias"]
    ).round(2)

    return serie


def serie_temporal(df):
    """Atajo: construye la serie de cortes ya con las variaciones."""
    return medir_evolucion(serie_de_cortes(df))


# ============================================================
# VISTAS AGREGADAS
# ============================================================

COLUMNAS_ANUALES = [
    "anio", "cortes", "stock_cierre", "crecimiento_neto",
    "crecimiento_pct", "repoblaciones", "personas_por_registro",
    "registros_min", "registros_cierre",
]


def resumen_por_anio(serie):
    """
    Un registro por ano con el stock de cierre y el crecimiento real.

    El crecimiento del ano suma las variaciones de sus cortes
    comparables. Las repoblaciones se excluyen del calculo pero se
    reportan aparte en la columna repoblaciones, para que el lector vea
    el corte y no lo interprete como aumento.
    """
    if serie.empty:
        return pd.DataFrame(columns=COLUMNAS_ANUALES)

    filas = []

    for anio, grupo in serie.groupby("ANIO"):
        con_medida = grupo[grupo["variacion_neta"].notna()]

        filas.append({
            "anio": int(anio),
            "cortes": int(len(grupo)),
            "stock_cierre": int(grupo.iloc[-1]["stock"]),
            "crecimiento_neto": int(con_medida["variacion_neta"].sum()),
            "crecimiento_pct": round(
                con_medida["variacion_neta"].sum()
                / con_medida["stock_referencia"].iloc[0] * 100, 2
            ) if len(con_medida) else 0.0,
            "repoblaciones": int(grupo["es_repoblacion"].sum()),
            "personas_por_registro": round(
                grupo.iloc[-1]["personas_por_registro"], 2
            ),
            "registros_min": int(grupo["registros"].min()),
            "registros_cierre": int(grupo.iloc[-1]["registros"]),
        })

    return pd.DataFrame(filas).sort_values("anio").reset_index(drop=True)


def variacion_por_mes_del_ano(serie):
    """
    Variacion promedio segun el mes del calendario.

    Sirve para buscar comportamiento estacional. Se apoya solo en cortes
    comparables, porque las repoblaciones falsearian el promedio.
    """
    con_medida = serie[serie["variacion_neta"].notna()].copy()

    if con_medida.empty:
        return pd.DataFrame(columns=["mes", "variacion_media", "cortes"])

    resumen = (
        con_medida.groupby("MES", as_index=False)
        .agg(
            variacion_media=("variacion_neta", "mean"),
            cortes=("variacion_neta", "size"),
        )
        .rename(columns={"MES": "mes"})
    )

    resumen["variacion_media"] = resumen["variacion_media"].round(1)

    return resumen.sort_values("mes").reset_index(drop=True)


# ============================================================
# EVIDENCIAS DE LOS CONOCIMIENTOS
# ============================================================

def duracion_en_anos(serie):
    """
    Anos decorridos entre el primer y el ultimo corte.

    Se usa para enunciar el periodo en el texto, en lugar de escribir
    una cantidad fija que quedaria desactualizada si la fuente publica
    un corte nuevo.
    """
    if serie.empty:
        return 0.0

    dias = (serie.iloc[-1]["FECHA"] - serie.iloc[0]["FECHA"]).days
    return round(dias / 365.25, 2)


def mayor_repoblacion(serie):
    """
    La repoblacion mas grande de la serie, con su factor de exceso.

    Devuelve las filas de stock y referencia junto con cuantas veces
    el corte publicado supera al ultimo corte comparable. Es el factor
    que dimensiona el costo de leer el pico como si fuera real.
    """
    candidatos = serie[
        serie["es_repoblacion"] & serie["stock_referencia"].notna()
    ]

    if candidatos.empty:
        return None

    fila = candidatos.loc[candidatos["stock"].idxmax()]

    referencia = float(fila["stock_referencia"])

    return {
        "fecha": fila["FECHA"].date().isoformat(),
        "anio": int(fila["ANIO"]),
        "registros": int(fila["registros"]),
        "stock": int(fila["stock"]),
        "stock_referencia": int(referencia),
        "exceso": int(fila["stock"] - referencia),
        "factor": round(fila["stock"] / referencia, 2) if referencia else 0.0,
    }


def calendario_de_cortes(serie):
    """
    Como se distribuyen los cortes en el calendario de publicacion.

    La fuente no publica un corte por mes: hay anos con un solo corte y
    huecos de varios meses entre publicaciones. Medirlo es lo que
    permite sostener que la comparacion valida es por dia y no por mes.
    """
    if serie.empty:
        return None

    fechas = serie["FECHA"].sort_values()
    cortes_por_anio = serie.groupby(serie["FECHA"].dt.year).size()

    # Meses que abarca la serie frente a meses en los que se publico
    # algum corte. Los que faltan son los que no se pueden usar para un
    # analisis mensual.
    periodos = fechas.dt.to_period("M")
    meses_con_corte = len(periodos.unique())
    meses_totales = (
        (fechas.iloc[-1].year - fechas.iloc[0].year) * 12
        + (fechas.iloc[-1].month - fechas.iloc[0].month)
        + 1
    )

    huecos = fechas.diff().dt.days.dropna()
    hueco_maximo = int(huecos.max()) if not huecos.empty else 0
    del_hueco = int((huecos > 90).sum()) if not huecos.empty else 0

    return {
        "cortes_por_anio": [
            {"anio": int(anio), "cortes": int(cortes)}
            for anio, cortes in cortes_por_anio.items()
        ],
        "minimo_por_anio": int(cortes_por_anio.min()),
        "maximo_por_anio": int(cortes_por_anio.max()),
        "anio_mas_cortes": int(cortes_por_anio.idxmax()),
        "anio_menos_cortes": int(cortes_por_anio.idxmin()),
        "hueco_maximo_dias": hueco_maximo,
        "huecos_largos": del_hueco,
        "meses_con_corte": meses_con_corte,
        "meses_totales": meses_totales,
        "meses_sin_corte": max(meses_totales - meses_con_corte, 0),
    }


# ============================================================
# INDICADORES
# ============================================================

def indicadores(serie):
    """
    Los tres indicadores de la dimension temporal.

    stock_actual          Personas detenidas en el ultimo corte.
    crecimiento_total_pct Variacion del stock entre el primer y el
                          ultimo corte, que es la unica lectura
                          valida de la serie.
    ritmo_diario          Personas por dia de promedio en los cortes
                          comparables.

    Una combinacion de filtros puede quedar sin registros. En ese caso
    se devuelven los valores en cero en lugar de fallar, para que la
    pagina muestre un estado vacio y no un error 500.
    """
    if serie.empty:
        return {
            "stock_actual": 0,
            "fecha_stock_actual": "",
            "stock_inicial": 0,
            "fecha_stock_inicial": "",
            "crecimiento_total_pct": 0.0,
            "ritmo_diario": 0.0,
            "total_cortes": 0,
            "repoblaciones": 0,
            "cortes_comparables": 0,
            "periodo_mayor_aumento": None,
            "periodo_mayor_disminucion": None,
        }

    comparables = serie[serie["variacion_neta"].notna()]
    ultimo = serie.iloc[-1]
    primero = serie.iloc[0]

    stock_actual = int(ultimo["stock"])
    stock_inicial = int(primero["stock"])

    return {
        "stock_actual": stock_actual,
        "fecha_stock_actual": ultimo["FECHA"].date().isoformat(),
        "stock_inicial": stock_inicial,
        "fecha_stock_inicial": primero["FECHA"].date().isoformat(),
        "crecimiento_total_pct": round(
            (stock_actual / stock_inicial - 1) * 100, 2
        ) if stock_inicial else 0.0,
        "ritmo_diario": round(comparables["variacion_diaria"].mean(), 2)
        if not comparables.empty else 0.0,
        "total_cortes": int(len(serie)),
        "repoblaciones": int(serie["es_repoblacion"].sum()),
        "cortes_comparables": int(len(comparables)),
        "periodo_mayor_aumento": _periodo_extremo(comparables, mayor=True),
        "periodo_mayor_disminucion": _periodo_extremo(comparables, mayor=False),
    }


def _periodo_extremo(comparables, mayor=True):
    """Devuelve el periodo con la variacion mas alta o mas baja."""
    if comparables.empty:
        return None

    fila = (
        comparables.loc[comparables["variacion_neta"].idxmax()]
        if mayor
        else comparables.loc[comparables["variacion_neta"].idxmin()]
    )

    return {
        "fecha": fila["FECHA"].date().isoformat(),
        "variacion": int(fila["variacion_neta"]),
        "variacion_pct": round(float(fila["variacion_pct"]), 3),
        "dias": int(fila["dias"]) if pd.notna(fila["dias"]) else None,
    }


# ============================================================
# RECORTE TEMPORAL
# ============================================================

def anios_disponibles(serie):
    """Años con al menos un corte, en orden ascendente."""
    return sorted(int(anio) for anio in serie["ANIO"].dropna().unique())


def recortar_por_anio(serie, anio_desde=None, anio_hasta=None):
    """
    Recorta la serie a un rango de años, ambos inclusive.

    Se aplica sobre la serie ya construida y no sobre el DataFrame
    crudo: asi el primer corte del rango conserva la variacion
    calculada frente al corte anterior, aunque ese corte quede fuera
    de la ventana elegida.
    """
    resultado = serie

    if anio_desde is not None:
        resultado = resultado[resultado["ANIO"] >= int(anio_desde)]

    if anio_hasta is not None:
        resultado = resultado[resultado["ANIO"] <= int(anio_hasta)]

    return resultado.reset_index(drop=True)


# ============================================================
# FILTROS
# ============================================================

def filtrar(df, pais=None, situacion=None, genero=None):
    """
    Aplica los filtros del tablero sobre el DataFrame de cortes.

    Cada criterio busca varios nombres posibles porque el DataFrame
    puede venir crudo del CSV, con los nombres originales acentuados
    (PAIS PRISION, SITUACION JURIDICA), o ya normalizado por la capa de
    la dimension poblacional, que los renombra a PAIS y SITUACION.
    """
    criterios = {
        ("PAIS PRISIÓN", "PAIS"): pais,
        ("SITUACIÓN JURÍDICA", "SITUACION"): situacion,
        ("GÉNERO", "GENERO"): genero,
    }

    resultado = df

    for posibles, valor in criterios.items():
        if not valor:
            continue
        columna = ubicar_columna(resultado, list(posibles))
        if columna is None:
            continue
        resultado = resultado[resultado[columna].astype(str).eq(str(valor))]

    return resultado


# ============================================================
# EJECUCION DIRECTA
# ============================================================

def main():
    """
    Calcula los indicadores y los deja disponibles en data/analisis_temporal.

    Se ejecuta con:  python src/analisis_temporal.py
    """
    print("=" * 70)
    print("ANALISIS DE LA DIMENSION TEMPORAL")
    print("=" * 70)

    serie = serie_temporal(cargar_datos())

    indicadores_ = indicadores(serie)
    anual = resumen_por_anio(serie)
    por_mes = variacion_por_mes_del_ano(serie)
    pico = mayor_repoblacion(serie)
    calendario = calendario_de_cortes(serie)

    print("\nSerie de cortes")
    print("-" * 70)
    print("Cortes publicados        :", indicadores_["total_cortes"])
    print("Cortes comparables       :", indicadores_["cortes_comparables"])
    print("Repoblaciones masivas    :", indicadores_["repoblaciones"])
    print("Periodo de la serie      :",
          indicadores_["fecha_stock_inicial"], "a",
          indicadores_["fecha_stock_actual"])
    print("Duracion del periodo     :", duracion_en_anos(serie), "anos")

    print("\nIndicadores")
    print("-" * 70)
    print("Stock actual             : "
          f"{indicadores_['stock_actual']:,} personas")
    print("Crecimiento de la serie  : "
          f"{indicadores_['crecimiento_total_pct']}%")
    print("Ritmo diario promedio    : "
          f"{indicadores_['ritmo_diario']} personas/dia")

    print("\nRepoblaciones detectadas")
    print("-" * 70)
    for _, fila in serie[serie["es_repoblacion"]].iterrows():
        print(f"  {fila['FECHA'].date()}  "
              f"{int(fila['registros']):,} registros  "
              f"{int(fila['stock']):,} personas")

    if calendario:
        print("\nCalendario de publicacion")
        print("-" * 70)
        print("Cortes por ano          :",
              [f"{f['anio']}={f['cortes']}"
               for f in calendario["cortes_por_anio"]])
        print("Menor cantidad en un ano:",
              calendario["minimo_por_anio"], "(",
              calendario["anio_menos_cortes"], ")")
        print("Mayor cantidad en un ano:",
              calendario["maximo_por_anio"], "(",
              calendario["anio_mas_cortes"], ")")
        print("Huecos de mas de 90 dias:", calendario["huecos_largos"])
        print("Hueco maximo            :",
              calendario["hueco_maximo_dias"], "dias")

    print("\nResumen por ano")
    print("-" * 70)
    print(anual.to_string(index=False))

    if pico:
        print("\nMayor repoblacion")
        print("-" * 70)
        print(f"  {pico['fecha']}  {pico['registros']:,} registros  "
              f"{pico['stock']:,} personas  "
              f"({pico['factor']}x su referencia de "
              f"{pico['stock_referencia']:,})")

    print("\nVariacion promedio por mes del ano")
    print("-" * 70)
    print(por_mes.to_string(index=False))

    print("\nPeriodos extremos")
    print("-" * 70)
    for etiqueta, periodo in (
        ("Mayor aumento  ", indicadores_["periodo_mayor_aumento"]),
        ("Mayor disminucion", indicadores_["periodo_mayor_disminucion"]),
    ):
        print(f"{etiqueta} : {periodo['fecha']}  "
              f"{periodo['variacion']:+,} personas "
              f"({periodo['variacion_pct']:+.3f}%)")

    os.makedirs(RUTA_SALIDA, exist_ok=True)

    serie.to_csv(os.path.join(RUTA_SALIDA, "serie_cortes.csv"),
                 index=False, encoding="utf-8-sig")
    anual.to_csv(os.path.join(RUTA_SALIDA, "resumen_anual.csv"),
                 index=False, encoding="utf-8-sig")
    por_mes.to_csv(os.path.join(RUTA_SALIDA, "variacion_por_mes.csv"),
                   index=False, encoding="utf-8-sig")
    print("\nArchivos generados en:", RUTA_SALIDA)


if __name__ == "__main__":
    main()
