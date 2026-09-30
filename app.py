from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import plotly.express as px
import numpy as np
from plotly.subplots import make_subplots
import os
import re
import unicodedata

from src import analisis_temporal as temporal


app = Flask(__name__)


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.path.join(
    BASE_DIR,
    "data",
    "Colombianos_detenidos_en_el_exterior.csv"
)


# ============================================================
# CACHÉ EN MEMORIA DEL DATASET PROCESADO
# ============================================================

_CACHE_DATASET = {}


# ============================================================
# MAPA DE PAÍSES → CÓDIGO ISO (para banderas)
# ============================================================

MAPA_PAISES_ISO = {
    "espana": "es", "mexico": "mx", "panama": "pa", "peru": "pe",
    "venezuela": "ve", "ecuador": "ec", "chile": "cl", "brasil": "br",
    "bolivia": "bo", "argentina": "ar", "colombia": "co",
    "estados unidos": "us", "eeuu": "us", "usa": "us",
    "costa rica": "cr", "italia": "it", "reino unido": "gb",
    "gran bretana": "gb", "francia": "fr", "alemania": "de",
    "canada": "ca", "portugal": "pt", "suiza": "ch",
    "paises bajos": "nl", "holanda": "nl", "belgica": "be",
    "austria": "at", "australia": "au", "japon": "jp", "china": "cn",
    "india": "in", "sudafrica": "za", "republica dominicana": "do",
    "cuba": "cu", "haiti": "ht", "honduras": "hn", "guatemala": "gt",
    "el salvador": "sv", "nicaragua": "ni", "paraguay": "py",
    "uruguay": "uy", "surinam": "sr", "guyana": "gy",
    "trinidad y tobago": "tt", "rusia": "ru", "turquia": "tr",
    "grecia": "gr", "irlanda": "ie", "noruega": "no", "suecia": "se",
    "dinamarca": "dk", "finlandia": "fi", "polonia": "pl",
    "corea del sur": "kr", "corea": "kr", "israel": "il",
    "arabia saudita": "sa", "emiratos arabes unidos": "ae",
    "marruecos": "ma", "argelia": "dz", "egipto": "eg",
}


# ============================================================
# UTILIDADES GENERALES
# ============================================================

def sin_acentos(texto):
    """Devuelve el texto en minúsculas, sin tildes ni diacríticos."""
    if texto is None:
        return ""
    texto = str(texto).strip().lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def reparar_mojibake(texto):
    """Intenta reparar secuencias mal codificadas tipo UTF-8/Latin-1."""
    if texto is None or pd.isna(texto):
        return ""
    t = str(texto)
    try:
        t = t.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    return t.replace("\ufffd", "").strip()


# ============================================================
# NORMALIZADORES POR VARIABLE
# ------------------------------------------------------------
# Cada normalizador mapea todas las variantes conocidas a un
# valor canónico único. Se aplican ANTES de agrupar, así se
# evita que categorías como "EN INVESTIGACIÓN" y "EN
# INVESTIGACIN" (sin tilde) queden separadas.
# ============================================================

def normalizar_delito(texto):
    """Normaliza los nombres de los delitos (repara acentos perdidos)."""
    if texto is None or pd.isna(texto):
        return "Sin información"

    t = reparar_mojibake(texto)
    lower = sin_acentos(t)

    patrones = [
        (r"narcotr.?fico",              "Narcotráfico"),
        (r"narcotrafico",               "Narcotráfico"),
        (r"robo\s*/\s*hurto",           "Robo / Hurto"),
        (r"hurto",                      "Hurto"),
        (r"homicidio\s*/\s*tentativa",  "Homicidio / Tentativa"),
        (r"homicidio",                  "Homicidio"),
        (r"delitos sexuales",           "Delitos sexuales"),
        (r"porte ilegal de armas",      "Porte ilegal de armas"),
        (r"secuestro",                  "Secuestro"),
        (r"fraude\s*/\s*estafa",        "Fraude / Estafa"),
        (r"crimen organizado",          "Crimen organizado"),
        (r"lavado de activos",          "Lavado de activos"),
        (r"contrabando",                "Contrabando"),
        (r"violencia intrafamiliar",    "Violencia intrafamiliar"),
        (r"desacato a la autoridad",    "Desacato a la autoridad"),
        (r"violencia de genero",        "Violencia de género"),
        (r"extorsion",                  "Extorsión"),
        (r"trata de personas",          "Trata de personas"),
        (r"terrorismo",                 "Terrorismo"),
        (r"conduccion temeraria",       "Conducción temeraria"),
        (r"amenazas",                   "Amenazas"),
        (r"delito migratorio",          "Delito migratorio"),
        (r"desconocido",                "Desconocido"),
        (r"no reporta",                 "No reporta / Confidencialidad"),
        (r"otros",                      "Otros"),
        (r"danos",                      "Daños"),
        (r"falsedad",                   "Falsedad en documento"),
        (r"falsificacion",              "Falsificación"),
        (r"allanamiento",               "Allanamiento"),
        (r"coaccion",                   "Coacción"),
        (r"delitos politicos",          "Delitos políticos"),
        (r"falso testimonio",           "Falso testimonio"),
        (r"celebracion indebida",       "Celebración indebida de contratos"),
    ]

    for patron, valor in patrones:
        if re.search(patron, lower):
            return valor

    return t.strip().capitalize()


def normalizar_pais(texto):
    """Normaliza el nombre del país."""
    if texto is None or pd.isna(texto):
        return "Sin información"

    t = reparar_mojibake(texto)
    lower = sin_acentos(t)

    patrones = [
        (r"espana",              "España"),
        (r"mexico",              "México"),
        (r"panama",              "Panamá"),
        (r"peru",                "Perú"),
        (r"venezuela",           "Venezuela"),
        (r"ecuador",             "Ecuador"),
        (r"chile",               "Chile"),
        (r"brasil",              "Brasil"),
        (r"bolivia",             "Bolivia"),
        (r"argentina",           "Argentina"),
        (r"colombia",            "Colombia"),
        (r"estados unidos",      "Estados Unidos"),
        (r"^ee\.?\s*uu\.?$",     "Estados Unidos"),
        (r"^usa$",               "Estados Unidos"),
        (r"costa rica",          "Costa Rica"),
        (r"italia",              "Italia"),
        (r"reino unido",         "Reino Unido"),
        (r"francia",             "Francia"),
        (r"alemania",            "Alemania"),
        (r"canada",              "Canadá"),
        (r"portugal",            "Portugal"),
        (r"suiza",               "Suiza"),
        (r"paises bajos",        "Países Bajos"),
        (r"holanda",             "Países Bajos"),
        (r"belgica",             "Bélgica"),
        (r"austria",             "Austria"),
        (r"australia",           "Australia"),
        (r"japon",               "Japón"),
        (r"china",               "China"),
        (r"india",               "India"),
        (r"sudafrica",           "Sudáfrica"),
        (r"republica dominicana","República Dominicana"),
        (r"cuba",                "Cuba"),
        (r"haiti",               "Haití"),
        (r"honduras",            "Honduras"),
        (r"guatemala",           "Guatemala"),
        (r"el salvador",         "El Salvador"),
        (r"nicaragua",           "Nicaragua"),
        (r"paraguay",            "Paraguay"),
        (r"uruguay",             "Uruguay"),
    ]

    for patron, valor in patrones:
        if re.search(patron, lower):
            return valor

    return t.strip().title()


def normalizar_situacion(texto):
    """
    Normaliza la SITUACIÓN JURÍDICA.

    Este normalizador es clave porque en el CSV conviven
    variantes con y sin tilde para la misma categoría
    (por ejemplo "EN INVESTIGACIÓN" y "EN INVESTIGACIN",
    o "EN ESPERA DE DEPORTACIÓN" y "EN ESPERA DE DEPORTACIN").
    Se mapean todas a un único valor canónico.
    """
    if texto is None or pd.isna(texto):
        return "Sin información"

    t = reparar_mojibake(texto)
    lower = sin_acentos(t)  # eliminamos tildes para comparar

    patrones = [
        (r"^condenad",                          "Condenado"),
        (r"investigaci",                        "En investigación"),
        (r"^en juicio",                         "En juicio"),
        (r"espera de deportaci",                "En espera de deportación"),
        (r"^deportaci",                         "En espera de deportación"),
        (r"^extraditad",                        "Extraditado"),
        (r"no reporta",                         "No reporta / Confidencialidad"),
        (r"confidencialidad",                   "No reporta / Confidencialidad"),
        (r"^sin informaci",                     "Sin información"),
    ]

    for patron, valor in patrones:
        if re.search(patron, lower):
            return valor

    return t.strip().capitalize()


def normalizar_genero(texto):
    """Normaliza el género para agrupar variantes."""
    if texto is None or pd.isna(texto):
        return "Sin información"

    t = reparar_mojibake(texto)
    lower = sin_acentos(t)

    if "masc" in lower:
        return "Masculino"
    if "fem" in lower:
        return "Femenino"
    if "no binari" in lower:
        return "No binario"
    if lower in {"otro", "otros", "otra"}:
        return "Otro"
    if lower in {"", "sin informacion", "desconocido", "no reporta"}:
        return "Sin información"

    return t.strip().capitalize()


def normalizar_edad(texto):
    """Normaliza el grupo de edad."""
    if texto is None or pd.isna(texto):
        return "Sin información"

    t = reparar_mojibake(texto)
    lower = sin_acentos(t)

    if "primera infancia" in lower:
        return "Primera infancia"
    if "infante" in lower:
        return "Infante"
    if "adolescente" in lower:
        return "Adolescente"
    if "adulto joven" in lower:
        return "Adulto joven"
    if "adulto mayor" in lower:
        return "Adulto mayor"
    if "adulto" in lower:
        return "Adulto"
    if lower in {"", "sin informacion", "desconocido", "no reporta"}:
        return "Sin información"

    return t.strip().capitalize()


def obtener_bandera(pais):
    """Devuelve la URL de la bandera del país o None."""
    if not pais:
        return None
    codigo = MAPA_PAISES_ISO.get(sin_acentos(pais))
    if codigo:
        return f"https://flagcdn.com/w80/{codigo}.png"
    return None


# ============================================================
# CARGA DEL CSV (crudo)
# ============================================================

def cargar_dataset_poblacional():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"No se encontró el dataset en: {DATA_PATH}"
        )
    try:
        df = pd.read_csv(DATA_PATH, encoding="utf-8", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(DATA_PATH, encoding="latin-1", low_memory=False)
    return df


def obtener_columna(df, posibles):
    columnas = {sin_acentos(col): col for col in df.columns}
    for nombre in posibles:
        clave = sin_acentos(nombre)
        if clave in columnas:
            return columnas[clave]
    raise KeyError(
        "No se encontró ninguna de las columnas esperadas: "
        + ", ".join(posibles)
    )


# ============================================================
# DATASET PROCESADO Y CACHEADO
# ============================================================

def cargar_dataset_procesado():
    if "df" in _CACHE_DATASET:
        return _CACHE_DATASET["df"]

    df = cargar_dataset_poblacional()

    col_cantidad  = obtener_columna(df, ["CANTIDAD", "cantidad"])
    col_genero    = obtener_columna(df, ["GÉNERO", "GENERO", "genero"])
    col_edad      = obtener_columna(df, ["GRUPO EDAD", "GRUPO_EDAD", "grupo_edad"])
    col_pais      = obtener_columna(df, ["PAIS PRISIÓN", "PAIS PRISION", "pais_prision"])
    col_delito    = obtener_columna(df, ["DELITO", "delito"])
    col_situacion = obtener_columna(
        df,
        ["SITUACIÓN JURÍDICA", "SITUACION JURIDICA", "situacion_juridica"]
    )

    df = df.rename(columns={
        col_cantidad:  "CANTIDAD",
        col_genero:    "GENERO",
        col_edad:      "EDAD",
        col_pais:      "PAIS",
        col_delito:    "DELITO",
        col_situacion: "SITUACION",
    })

    df["CANTIDAD"] = pd.to_numeric(df["CANTIDAD"], errors="coerce").fillna(0)

    # --------------------------------------------------------
    # Normalización (todas las variantes → valor canónico)
    # --------------------------------------------------------

    df["GENERO"]    = df["GENERO"].apply(normalizar_genero)
    df["EDAD"]      = df["EDAD"].apply(normalizar_edad)
    df["PAIS"]      = df["PAIS"].apply(normalizar_pais)
    df["DELITO"]    = df["DELITO"].apply(normalizar_delito)
    df["SITUACION"] = df["SITUACION"].apply(normalizar_situacion)

    _CACHE_DATASET["df"] = df
    return df


# ============================================================
# GENERADORES DE INTERPRETACIÓN DINÁMICA
# ============================================================

def _contexto_filtros(pais, edad):
    if pais and edad:
        return f"Al filtrar por <em>{pais}</em> y el grupo etario <em>{edad}</em>"
    if pais:
        return f"Al filtrar por <em>{pais}</em>"
    if edad:
        return f"Al filtrar por el grupo etario <em>{edad}</em>"
    return "En el total de la población sin filtros"


def interpretacion_genero(genero_df, pais, edad):
    if genero_df.empty or genero_df["cantidad"].sum() == 0:
        return "No hay información suficiente para los filtros seleccionados."

    # Defensivo: ordenamos descendente para que iloc[0] sea el predominante
    genero_df = genero_df.sort_values("cantidad", ascending=False).reset_index(drop=True)

    top = genero_df.iloc[0]
    contexto = _contexto_filtros(pais, edad)

    texto = (
        f"{contexto}, el género <em>{top['categoria']}</em> concentra "
        f"el <strong>{top['porcentaje']:.2f}%</strong> "
        f"({top['cantidad']:,.0f} personas)."
    )

    if len(genero_df) > 1:
        seg = genero_df.iloc[1]
        texto += (
            f" Le sigue <em>{seg['categoria']}</em> con el "
            f"{seg['porcentaje']:.2f}% ({seg['cantidad']:,.0f} personas)."
        )

    if pais or edad:
        texto += (
            " El predominio masculino se mantiene incluso con los filtros "
            "aplicados, lo que confirma su carácter estructural."
        )
    else:
        texto += (
            " Este patrón fuertemente masculinizado es estable a nivel "
            "nacional y sugiere un sesgo de género estructural en las "
            "detenciones en el exterior."
        )

    return texto


def interpretacion_situacion(situacion_df, pais, edad):
    if situacion_df.empty or situacion_df["cantidad"].sum() == 0:
        return "No hay información suficiente para los filtros seleccionados."

    # CLAVE: la tabla original viene ordenada ascendente para la gráfica
    # horizontal. Aquí reordenamos descendente para tomar el predominante.
    situacion_df = situacion_df.sort_values("cantidad", ascending=False).reset_index(drop=True)

    top = situacion_df.iloc[0]
    contexto = _contexto_filtros(pais, edad)

    texto = (
        f"{contexto}, la situación jurídica predominante es "
        f"<em>{top['categoria']}</em> con el "
        f"<strong>{top['porcentaje']:.2f}%</strong> "
        f"({top['cantidad']:,.0f} personas)."
    )

    if len(situacion_df) > 1:
        seg = situacion_df.iloc[1]
        texto += (
            f" Le sigue <em>{seg['categoria']}</em> "
            f"con el {seg['porcentaje']:.2f}% "
            f"({seg['cantidad']:,.0f} personas)."
        )

    if pais or edad:
        texto += (
            " La composición procesal puede variar según el país y el "
            "grupo etario, lo que permite priorizar acciones consulares "
            "diferenciadas por contexto."
        )
    else:
        texto += (
            " La elevada proporción de condenados indica que la mayoría "
            "de los casos ya están judicialmente resueltos, mientras que "
            "un tercio permanece en fase de instrucción."
        )

    return texto


def interpretacion_delito(delito_df, pais, edad):
    if delito_df.empty or delito_df["cantidad"].sum() == 0:
        return "No hay información suficiente para los filtros seleccionados."

    delito_df = delito_df.sort_values("cantidad", ascending=False).reset_index(drop=True)

    top = delito_df.iloc[0]
    contexto = _contexto_filtros(pais, edad)

    texto = (
        f"{contexto}, el delito predominante es <em>{top['categoria']}</em> "
        f"con el <strong>{top['porcentaje']:.2f}%</strong> de los casos "
        f"({top['cantidad']:,.0f} personas)."
    )

    if len(delito_df) >= 3:
        seg = delito_df.iloc[1]
        ter = delito_df.iloc[2]
        texto += (
            f" Le siguen <em>{seg['categoria']}</em> "
            f"({seg['porcentaje']:.2f}%) y <em>{ter['categoria']}</em> "
            f"({ter['porcentaje']:.2f}%)."
        )

    if pais or edad:
        texto += (
            " El perfil delictivo cambia según el contexto seleccionado, "
            "lo que permite identificar prioridades penales diferenciadas "
            "por país y grupo etario."
        )
    else:
        texto += (
            " La fuerte concentración en narcotráfico refleja el perfil "
            "delictivo predominante a nivel general y orienta la política "
            "criminal hacia este tipo penal."
        )

    return texto


# ============================================================
# RUTAS GENERALES
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/dimension-1')
def dimension_1():
    return redirect(url_for('dimension_poblacional'))


@app.route('/dimension-2')
def dimension_2():
    return render_template('dim_2.html', titulo="Dimensión 2")


@app.route('/dimension-3')
def dimension_3():
    return redirect(url_for('dimension_temporal'))


@app.route('/dimension-4')
def dimension_4():
    return render_template('dim_4.html', titulo="Dimensión 4")


# ============================================================
# DIMENSIÓN POBLACIONAL
# ============================================================

@app.route('/dimension-poblacional')
def dimension_poblacional():

    # --------------------------------------------------------
    # 1. DATASET PROCESADO (caché)
    # --------------------------------------------------------

    df_base = cargar_dataset_procesado()

    if "lista_paises" not in _CACHE_DATASET:
        _CACHE_DATASET["lista_paises"] = sorted(
            df_base["PAIS"].dropna().astype(str).unique().tolist()
        )
        _CACHE_DATASET["lista_edades"] = sorted(
            df_base["EDAD"].dropna().astype(str).unique().tolist()
        )

    lista_paises = _CACHE_DATASET["lista_paises"]
    lista_edades = _CACHE_DATASET["lista_edades"]

    # --------------------------------------------------------
    # 2. FILTROS
    # --------------------------------------------------------

    pais_filtro = request.args.get("pais", "").strip()
    edad_filtro = request.args.get("edad", "").strip()

    df = df_base

    if pais_filtro:
        df = df[df["PAIS"].eq(pais_filtro)]

    if edad_filtro:
        df = df[df["EDAD"].eq(edad_filtro)]

    # --------------------------------------------------------
    # 3. INDICADOR 1 — POBLACIÓN TOTAL
    # --------------------------------------------------------

    total_registros = int(len(df))
    poblacion_total = int(df["CANTIDAD"].sum())

    # --------------------------------------------------------
    # 4. DISTRIBUCIÓN POR GÉNERO
    # --------------------------------------------------------

    genero = (
        df.groupby("GENERO", dropna=False)["CANTIDAD"]
        .sum()
        .reset_index()
    )
    genero.columns = ["categoria", "cantidad"]
    genero["categoria"] = genero["categoria"].astype(str)

    total_genero = genero["cantidad"].sum()
    genero["porcentaje"] = (
        genero["cantidad"] / total_genero * 100 if total_genero > 0 else 0
    )
    genero = genero.sort_values("cantidad", ascending=False)

    # --------------------------------------------------------
    # 5. INDICADOR 2 — GÉNERO PREDOMINANTE
    # --------------------------------------------------------

    if not genero.empty:
        genero_predominante = genero.iloc[0]["categoria"]
        porcentaje_genero = float(genero.iloc[0]["porcentaje"])
    else:
        genero_predominante = "SIN DATOS"
        porcentaje_genero = 0.0

    # --------------------------------------------------------
    # 6. DISTRIBUCIÓN POR SITUACIÓN JURÍDICA
    # --------------------------------------------------------

    situacion = (
        df.groupby("SITUACION", dropna=False)["CANTIDAD"]
        .sum()
        .reset_index()
    )
    situacion.columns = ["categoria", "cantidad"]
    situacion["categoria"] = situacion["categoria"].astype(str)

    total_situacion = situacion["cantidad"].sum()
    situacion["porcentaje"] = (
        situacion["cantidad"] / total_situacion * 100
        if total_situacion > 0 else 0
    )

    # Para la GRÁFICA horizontal: menor arriba, mayor abajo
    situacion = situacion.sort_values("cantidad", ascending=True)

    # --------------------------------------------------------
    # 7. DISTRIBUCIÓN POR DELITO (TOP 8)
    # --------------------------------------------------------

    delito = (
        df.groupby("DELITO", dropna=False)["CANTIDAD"]
        .sum()
        .reset_index()
    )
    delito.columns = ["categoria", "cantidad"]
    delito["categoria"] = delito["categoria"].astype(str)

    total_delito = delito["cantidad"].sum()
    delito["porcentaje"] = (
        delito["cantidad"] / total_delito * 100 if total_delito > 0 else 0
    )
    delito = delito.sort_values("cantidad", ascending=False)

    # --------------------------------------------------------
    # 8. INDICADOR 3 — DELITO PREDOMINANTE
    # --------------------------------------------------------

    if not delito.empty:
        delito_predominante = delito.iloc[0]["categoria"]
        porcentaje_delito = float(delito.iloc[0]["porcentaje"])
    else:
        delito_predominante = "SIN DATOS"
        porcentaje_delito = 0.0

    top_delitos = delito.head(8).copy()

    # ========================================================
    # GRÁFICA 1 — GÉNERO (DONA)
    # ========================================================

    fig_genero = px.pie(
        genero,
        names="categoria",
        values="cantidad",
        hole=0.55,
        color="categoria",
        color_discrete_sequence=[
            "#00f0ff", "#ff2bd1", "#7affb2",
            "#ffb703", "#a259ff", "#ff6b6b"
        ],
    )

    fig_genero.update_traces(
        textinfo="percent+label",
        textfont_size=12,
        marker=dict(line=dict(color="#0a0a0a", width=2)),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Personas: %{value:,.0f}<br>"
            "%{percent}<extra></extra>"
        )
    )

    fig_genero.update_layout(
        template="plotly_dark",
        height=440,
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=20, b=20),
        font=dict(family="Share Tech Mono, monospace"),
    )

    grafica_genero = fig_genero.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        config={"displayModeBar": False}
    )

    # ========================================================
    # GRÁFICA 2 — SITUACIÓN JURÍDICA
    # ========================================================

    fig_situacion = px.bar(
        situacion,
        x="cantidad",
        y="categoria",
        orientation="h",
        text="porcentaje",
        color="cantidad",
        color_continuous_scale=["#0a1a2f", "#00f0ff", "#ff2bd1"],
        labels={
            "categoria": "Situación jurídica",
            "cantidad": "Personas",
            "porcentaje": "%"
        }
    )

    fig_situacion.update_traces(
        texttemplate="%{text:.2f}%",
        textposition="outside"
    )

    fig_situacion.update_layout(
        template="plotly_dark",
        height=440,
        coloraxis_showscale=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=30, r=30, t=30, b=40),
        font=dict(family="Share Tech Mono, monospace"),
        xaxis=dict(gridcolor="rgba(0,240,255,0.08)"),
        yaxis=dict(gridcolor="rgba(0,240,255,0.08)")
    )

    grafica_situacion = fig_situacion.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": False}
    )

    # ========================================================
    # GRÁFICA 3 — DELITO (TORTA)
    # ========================================================

    fig_delito = px.pie(
        top_delitos,
        names="categoria",
        values="cantidad",
        color="categoria",
        color_discrete_sequence=px.colors.qualitative.Bold,
        hole=0.35
    )

    fig_delito.update_traces(
        textinfo="percent",
        textfont_size=12,
        textposition="inside",
        marker=dict(line=dict(color="#0a0a0a", width=2)),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Personas: %{value:,.0f}<br>"
            "Porcentaje: %{percent}<extra></extra>"
        )
    )

    fig_delito.update_layout(
        template="plotly_dark",
        height=560,
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.02,
            font=dict(size=11)
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=20, b=20),
        font=dict(family="Share Tech Mono, monospace"),
    )

    grafica_delito = fig_delito.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": False}
    )

    # ========================================================
    # INTERPRETACIONES DINÁMICAS
    # ========================================================

    interp_genero    = interpretacion_genero(genero, pais_filtro, edad_filtro)
    interp_situacion = interpretacion_situacion(situacion, pais_filtro, edad_filtro)
    interp_delito    = interpretacion_delito(delito, pais_filtro, edad_filtro)

    # ========================================================
    # BANDERA DEL PAÍS SELECCIONADO
    # ========================================================

    bandera_url = obtener_bandera(pais_filtro) if pais_filtro else None

    # ========================================================
    # RENDER
    # ========================================================

    return render_template(
        'dim_1.html',

        titulo="Dimensión Poblacional",

        total_registros=total_registros,
        poblacion_total=poblacion_total,

        genero_predominante=genero_predominante,
        porcentaje_genero=porcentaje_genero,

        delito_predominante=delito_predominante,
        porcentaje_delito=porcentaje_delito,

        grafica_genero=grafica_genero,
        grafica_situacion=grafica_situacion,
        grafica_delito=grafica_delito,

        interp_genero=interp_genero,
        interp_situacion=interp_situacion,
        interp_delito=interp_delito,

        lista_paises=lista_paises,
        lista_edades=lista_edades,

        pais_seleccionado=pais_filtro,
        edad_seleccionada=edad_filtro,

        bandera_url=bandera_url,
    )


# ============================================================
# PÁGINA DE ANÁLISIS / DOCUMENTACIÓN
# ============================================================

@app.route('/analisis-poblacional')
def analisis_poblacional():

    df = cargar_dataset_procesado()

    # ========================================================
    # GRÁFICA K1 — GÉNERO
    # ========================================================

    genero = (
        df.groupby("GENERO", dropna=False)["CANTIDAD"]
        .sum()
        .reset_index()
    )
    genero.columns = ["categoria", "cantidad"]
    genero = genero.sort_values("cantidad", ascending=False)

    fig_k1 = px.pie(
        genero,
        names="categoria",
        values="cantidad",
        hole=0.55,
        color="categoria",
        color_discrete_sequence=[
            "#00f0ff", "#ff2bd1", "#7affb2",
            "#ffb703", "#a259ff", "#ff6b6b"
        ],
    )
    fig_k1.update_traces(
        textinfo="percent+label",
        textfont_size=11,
        marker=dict(line=dict(color="#0a0a0a", width=2)),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Personas: %{value:,.0f}<br>"
            "%{percent}<extra></extra>"
        )
    )
    fig_k1.update_layout(
        template="plotly_dark",
        height=380,
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        font=dict(family="Share Tech Mono, monospace", size=11),
    )

    grafica_k1 = fig_k1.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        config={"displayModeBar": False}
    )

    # ========================================================
    # GRÁFICA K2 — SITUACIÓN JURÍDICA
    # ========================================================

    situacion = (
        df.groupby("SITUACION", dropna=False)["CANTIDAD"]
        .sum()
        .reset_index()
    )
    situacion.columns = ["categoria", "cantidad"]
    situacion = situacion.sort_values("cantidad", ascending=True)

    fig_k2 = px.bar(
        situacion,
        x="cantidad",
        y="categoria",
        orientation="h",
        text="cantidad",
        color="cantidad",
        color_continuous_scale=["#0a1a2f", "#00f0ff", "#ff2bd1"],
    )
    fig_k2.update_traces(
        texttemplate="%{text:,.0f}",
        textposition="outside"
    )
    fig_k2.update_layout(
        template="plotly_dark",
        height=380,
        coloraxis_showscale=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        font=dict(family="Share Tech Mono, monospace", size=11),
        xaxis=dict(gridcolor="rgba(0,240,255,0.08)"),
        yaxis=dict(gridcolor="rgba(0,240,255,0.08)"),
    )

    grafica_k2 = fig_k2.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": False}
    )

    # ========================================================
    # GRÁFICA K3 — DELITO (TOP 8)
    # ========================================================

    delito = (
        df.groupby("DELITO", dropna=False)["CANTIDAD"]
        .sum()
        .reset_index()
    )
    delito.columns = ["categoria", "cantidad"]
    delito = delito.sort_values("cantidad", ascending=False)

    top_delitos = delito.head(8).copy()

    fig_k3 = px.pie(
        top_delitos,
        names="categoria",
        values="cantidad",
        color="categoria",
        color_discrete_sequence=px.colors.qualitative.Bold,
        hole=0.35
    )
    fig_k3.update_traces(
        textinfo="percent",
        textfont_size=11,
        textposition="inside",
        marker=dict(line=dict(color="#0a0a0a", width=2)),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Personas: %{value:,.0f}<br>"
            "Porcentaje: %{percent}<extra></extra>"
        )
    )
    fig_k3.update_layout(
        template="plotly_dark",
        height=420,
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.02,
            font=dict(size=10)
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        font=dict(family="Share Tech Mono, monospace", size=11),
    )

    grafica_k3 = fig_k3.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": False}
    )

    return render_template(
        'analisis_poblacional.html',
        grafica_k1=grafica_k1,
        grafica_k2=grafica_k2,
        grafica_k3=grafica_k3,
    )


# ============================================================
# DIMENSIÓN TEMPORAL
# ------------------------------------------------------------
# El detalle metodológico de por qué la comparación se hace entre
# cortes y no de forma acumulada está documentado en
# src/analisis_temporal.py.
# ============================================================

@app.route('/dimension-temporal')
def dimension_temporal():

    # --------------------------------------------------------
    # 1. FILTROS
    # --------------------------------------------------------

    pais_filtro = request.args.get("pais", "").strip()
    situacion_filtro = request.args.get("situacion", "").strip()

    # Se reutiliza la capa de datos ya normalizada por la dimensión
    # poblacional. Así los valores de los filtros coinciden con los
    # de las demás dimensiones y el costo se paga una sola vez por
    # proceso.
    df_base = cargar_dataset_procesado()

    if "lista_situaciones" not in _CACHE_DATASET:
        _CACHE_DATASET["lista_situaciones"] = sorted(
            df_base["SITUACION"].dropna().astype(str).unique().tolist()
        )

    lista_paises = _CACHE_DATASET.get(
        "lista_paises",
        sorted(df_base["PAIS"].dropna().astype(str).unique().tolist())
    )
    lista_situaciones = _CACHE_DATASET["lista_situaciones"]

    # --------------------------------------------------------
    # 2. SERIE DE CORTES Y EVOLUCIÓN
    # --------------------------------------------------------

    df_filtrado = temporal.filtrar(
        df_base,
        pais=pais_filtro,
        situacion=situacion_filtro,
    )

    serie = temporal.serie_temporal(df_filtrado)
    indicadores = temporal.indicadores(serie)
    anual = temporal.resumen_por_anio(serie)
    por_mes = temporal.variacion_por_mes_del_ano(serie)

    # Una combinación de filtros puede quedar sin registros. En ese
    # caso no se construyen las gráficas: se devuelve el tablero con un
    # aviso para que el usuario revise o quite los filtros.
    sin_datos = serie.empty

    if sin_datos:
        return render_template(
            'dim_3.html',
            titulo="Dimensión Temporal",
            sin_datos=True,
            lista_paises=lista_paises,
            lista_situaciones=lista_situaciones,
            pais_seleccionado=pais_filtro,
            situacion_seleccionada=situacion_filtro,
        )

    # --------------------------------------------------------
    # 3. GRÁFICA 1 — STOCK POR CORTE
    # --------------------------------------------------------

    serie_grafica = serie.copy()
    serie_grafica["TIPO"] = np.where(
        serie_grafica["es_repoblacion"],
        "Republicacion masiva",
        "Corte comparable",
    )

    fig_stock = px.line(
        serie_grafica,
        x="FECHA",
        y="stock",
        color="TIPO",
        markers=True,
        color_discrete_map={
            "Corte comparable": "#00f0ff",
            "Republicacion masiva": "#ff0055",
        },
        labels={
            "FECHA": "Fecha de corte",
            "stock": "Personas detenidas",
            "TIPO": "",
        },
    )

    fig_stock.update_traces(
        line=dict(width=2),
        marker=dict(size=6),
        hovertemplate=(
            "<b>%{x|%d/%m/%Y}</b><br>"
            "Stock: %{y:,.0f} personas<extra></extra>"
        ),
    )

    fig_stock.update_layout(
        template="plotly_dark",
        height=460,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=30, b=20),
        font=dict(family="Share Tech Mono, monospace"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis=dict(gridcolor="rgba(0,240,255,0.08)"),
        yaxis=dict(gridcolor="rgba(0,240,255,0.08)"),
    )

    grafica_stock = fig_stock.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        config={"displayModeBar": False},
    )

    # --------------------------------------------------------
    # 4. GRÁFICA 2 — VARIACIÓN NETA ENTRE CORTES
    # --------------------------------------------------------

    comparables = serie[serie["variacion_neta"].notna()].copy()
    comparables["MOVIMIENTO"] = np.where(
        comparables["variacion_neta"] >= 0,
        "Aumento",
        "Disminucion",
    )

    fig_variacion = px.bar(
        comparables,
        x="FECHA",
        y="variacion_neta",
        color="MOVIMIENTO",
        color_discrete_map={
            "Aumento": "#7affb2",
            "Disminucion": "#ff6b6b",
        },
        labels={
            "FECHA": "Fecha de corte",
            "variacion_neta": "Personas frente al corte anterior",
            "MOVIMIENTO": "",
        },
    )

    fig_variacion.add_hline(
        y=0, line_width=1, line_dash="dot", line_color="rgba(255,255,255,0.35)"
    )

    fig_variacion.update_traces(
        hovertemplate=(
            "<b>%{x|%d/%m/%Y}</b><br>"
            "Variacion: %{y:+,.0f} personas<extra></extra>"
        ),
    )

    fig_variacion.update_layout(
        template="plotly_dark",
        height=420,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=30, b=20),
        font=dict(family="Share Tech Mono, monospace"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis=dict(gridcolor="rgba(0,240,255,0.08)"),
        yaxis=dict(gridcolor="rgba(0,240,255,0.08)"),
    )

    grafica_variacion = fig_variacion.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": False},
    )

    # --------------------------------------------------------
    # 5. GRÁFICA 3 — CIERRE Y CRECIMIENTO POR AÑO
    # --------------------------------------------------------

    fig_anual = px.bar(
        anual,
        x=anual["anio"].astype(str),
        y="crecimiento_neto",
        color="crecimiento_neto",
        color_continuous_scale=["#ff6b6b", "#0a1a2f", "#7affb2"],
        labels={
            "x": "Año",
            "crecimiento_neto": "Crecimiento neto del año",
            "color": "",
        },
    )

    fig_anual.add_scatter(
        x=anual["anio"].astype(str),
        y=anual["stock_cierre"],
        name="Stock de cierre",
        mode="lines+markers",
        line=dict(color="#ffb703", width=2),
        yaxis="y2",
        hovertemplate="Stock de cierre: %{y:,.0f}<extra></extra>",
    )

    fig_anual.add_hline(
        y=0, line_width=1, line_dash="dot", line_color="rgba(255,255,255,0.35)"
    )

    fig_anual.update_layout(
        template="plotly_dark",
        height=460,
        coloraxis_showscale=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=30, b=20),
        font=dict(family="Share Tech Mono, monospace"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis=dict(gridcolor="rgba(0,240,255,0.08)"),
        yaxis=dict(
            title="Crecimiento neto",
            gridcolor="rgba(0,240,255,0.08)",
        ),
        yaxis2=dict(
            title="Stock de cierre",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
    )

    grafica_anual = fig_anual.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": False},
    )

    # --------------------------------------------------------
    # 6. INTERPRETACIONES DINÁMICAS
    # --------------------------------------------------------

    contexto = []
    if pais_filtro:
        contexto.append(f"el país <em>{pais_filtro}</em>")
    if situacion_filtro:
        contexto.append(f"la situación jurídica <em>{situacion_filtro}</em>")
    texto_contexto = (
        "Al filtrar por " + " y ".join(contexto)
        if contexto
        else "En el total de la población sin filtros"
    )

    if indicadores["repoblaciones"]:
        nota_picos = (
            f"La serie es prácticamente plana: los picos visibles son las "
            f"{indicadores['repoblaciones']} republicaciones masivas, no un "
            f"aumento de detenidos."
        )
    else:
        nota_picos = "La serie no presenta saltos ni repoblaciones masivas."

    interp_stock = (
        f"{texto_contexto}, el stock de detenidos va de "
        f"<strong>{indicadores['stock_inicial']:,}</strong> personas el "
        f"{indicadores['fecha_stock_inicial']} a "
        f"<strong>{indicadores['stock_actual']:,}</strong> el "
        f"{indicadores['fecha_stock_actual']}, un "
        f"<strong>{indicadores['crecimiento_total_pct']:+.2f}%</strong> en todo "
        f"el periodo. {nota_picos}"
    )

    if not comparables.empty:
        sube = int((comparables["variacion_neta"] > 0).sum())
        interp_variacion = (
            f"{texto_contexto}, de los "
            f"{indicadores['cortes_comparables']} cortes comparables, "
            f"<strong>{sube}</strong> muestran aumento y "
            f"<strong>{len(comparables) - sube}</strong> muestran "
            f"disminución, con un ritmo promedio de "
            f"<strong>{indicadores['ritmo_diario']:+.2f} personas/día</strong>. "
            f"El movimiento es de corto aliento: la población sube y baja en "
            f"decenas o cientos de personas, nunca en miles."
        )
    else:
        interp_variacion = (
            "No hay cortes comparables para los filtros seleccionados."
        )

    if not por_mes.empty:
        mes_max = por_mes.loc[por_mes["variacion_media"].idxmax()]
        mes_min = por_mes.loc[por_mes["variacion_media"].idxmin()]
        nombres = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo",
            6: "junio", 7: "julio", 8: "agosto", 9: "septiembre",
            10: "octubre", 11: "noviembre", 12: "diciembre",
        }
        interp_anual = (
            f"Por mes del calendario, el mayor aumento promedio ocurre en "
            f"<em>{nombres.get(int(mes_max['mes']), mes_max['mes'])}</em> "
            f"({mes_max['variacion_media']:+,.0f} personas) y la mayor "
            f"disminución en <em>{nombres.get(int(mes_min['mes']), mes_min['mes'])}</em> "
            f"({mes_min['variacion_media']:+,.0f}). El estacional es débil: "
            f"la variación media del año entero es de unas décimas de personas "
            f"por corte."
        )
    else:
        interp_anual = "Sin datos suficientes para el análisis estacional."

    # --------------------------------------------------------
    # 7. DATOS DE LA TABLA DE REPUBLICACIONES
    # --------------------------------------------------------

    republicaciones = serie[serie["es_repoblacion"]].copy()
    filas_republicaciones = [
        {
            "fecha": fila["FECHA"].date().isoformat(),
            "registros": int(fila["registros"]),
            "stock": int(fila["stock"]),
            "exceso": int(fila["stock"] - fila["stock_referencia"]),
        }
        for _, fila in republicaciones.iterrows()
    ]

    filas_anuales = [
        {
            "anio": int(fila["anio"]),
            "cortes": int(fila["cortes"]),
            "stock_cierre": int(fila["stock_cierre"]),
            "crecimiento_neto": int(fila["crecimiento_neto"]),
            "crecimiento_pct": float(fila["crecimiento_pct"]),
            "repoblaciones": int(fila["repoblaciones"]),
            "personas_por_registro": float(fila["personas_por_registro"]),
        }
        for _, fila in anual.iterrows()
    ]

    filas_mes = [
        {
            "mes": int(fila["mes"]),
            "variacion_media": float(fila["variacion_media"]),
            "cortes": int(fila["cortes"]),
        }
        for _, fila in por_mes.iterrows()
    ]

    # --------------------------------------------------------
    # 8. RENDER
    # --------------------------------------------------------

    return render_template(
        'dim_3.html',

        titulo="Dimensión Temporal",
        sin_datos=False,

        stock_actual=indicadores["stock_actual"],
        fecha_stock_actual=indicadores["fecha_stock_actual"],
        crecimiento_total_pct=indicadores["crecimiento_total_pct"],
        ritmo_diario=indicadores["ritmo_diario"],
        total_cortes=indicadores["total_cortes"],
        cortes_comparables=indicadores["cortes_comparables"],
        repoblaciones=indicadores["repoblaciones"],
        stock_inicial=indicadores["stock_inicial"],
        fecha_stock_inicial=indicadores["fecha_stock_inicial"],

        grafica_stock=grafica_stock,
        grafica_variacion=grafica_variacion,
        grafica_anual=grafica_anual,

        interp_stock=interp_stock,
        interp_variacion=interp_variacion,
        interp_anual=interp_anual,

        filas_republicaciones=filas_republicaciones,
        filas_anuales=filas_anuales,
        filas_mes=filas_mes,

        lista_paises=lista_paises,
        lista_situaciones=lista_situaciones,
        pais_seleccionado=pais_filtro,
        situacion_seleccionada=situacion_filtro,
    )


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == '__main__':
    app.run(debug=True)