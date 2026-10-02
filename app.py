from flask import Flask, jsonify, render_template, request, redirect, url_for
import pandas as pd
import plotly.express as px
import numpy as np
from plotly.subplots import make_subplots
import os
import re
import unicodedata

from src import analisis_temporal as temporal
from src import dimension_territorial as territorial


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

NUMEROS_EN_PALABRAS = {
    0: "cero", 1: "uno", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco",
    6: "seis", 7: "siete", 8: "ocho", 9: "nueve", 10: "diez",
    11: "once", 12: "doce",
}


def en_palabras(numero, sufijo=""):
    """
    Escribe un número pequeño en palabras, para el texto de las páginas.

    Los tableros redactan conclusiones en prosa, y una cifra fija
    embebida en el HTML se desactualiza en cuanto la fuente publica un
    corte nuevo. Este helper permite que el dato siga viniendo del
    cálculo y solo se convierta en texto al renderizar.
    """
    entero = int(round(numero))

    if entero in NUMEROS_EN_PALABRAS:
        return f"{NUMEROS_EN_PALABRAS[entero]}{sufijo}"

    return f"{numero:,.0f}{sufijo}"


def anio_en_rango(texto, minimo, maximo, por_defecto):
    """
    Convierte un año recibido por la URL en un entero válido.

    El filtro del tablero temporal es un rango de años. Si el valor no
    es numérico o cae fuera de los años con cortes, se ajusta a los
    límites del conjunto, de modo que un enlace mal formado nunca deje
    el tablero vacío sin explicación.
    """
    if texto is None or str(texto).strip() == "":
        return por_defecto

    try:
        anio = int(str(texto).strip())
    except (TypeError, ValueError):
        return por_defecto

    return max(minimo, min(maximo, anio))


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

def normalizar_columna(serie, funcion):
    """
    Aplica una función de normalización a una columna categórica.

    Las columnas del dataset (país, delito, situación jurídica, género
    y grupo de edad) repiten los mismos valores cientos de veces cada
    una. Como las funciones de normalización solo dependen del texto de
    la celda, se calculan una vez por valor distinto y se proyectan con
    un map, en lugar de invocar la función 388.148 veces.

    El resultado es el mismo que el de `serie.apply(funcion)`, incluidas
    las celdas vacías, que se resuelven con la misma regla que usa la
    función para un valor ausente.
    """
    equivalentes = {
        valor: funcion(valor) for valor in serie.dropna().unique()
    }

    return serie.map(equivalentes).fillna(funcion(None))


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
    # Se normaliza sobre los valores distintos de cada columna y luego
    # se proyecta el resultado sobre todas las filas. Las cinco
    # funciones de normalización son puras (dependen solo del texto de
    # la celda), así que el resultado es idéntico al de recorrer las
    # 388.148 filas una por una, pero la carga inicial del dataset
    # baja de unos 13 segundos a menos de uno. En un despliegue eso es
    # la diferencia entre una primera visita lenta y un error por
    # tiempo de espera agotado.

    df["GENERO"]    = normalizar_columna(df["GENERO"], normalizar_genero)
    df["EDAD"]      = normalizar_columna(df["EDAD"], normalizar_edad)
    df["PAIS"]      = normalizar_columna(df["PAIS"], normalizar_pais)
    df["DELITO"]    = normalizar_columna(df["DELITO"], normalizar_delito)
    df["SITUACION"] = normalizar_columna(
        df["SITUACION"], normalizar_situacion
    )

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
    return redirect(url_for('dimension_territorial'))


@app.route('/dimension-3')
def dimension_3():
    return redirect(url_for('dimension_temporal'))


def _etiqueta_clave_relacional(valor):
    return re.sub(r"[^A-Z0-9]", "", sin_acentos(valor).replace("\ufffd", "").upper())


def datos_dimension_relacional():
    """Prepara las variables de la dimensión relacional con etiquetas canónicas."""
    base = cargar_dataset_procesado()
    datos = base[["PAIS", "DELITO", "SITUACION", "GENERO", "EDAD", "CANTIDAD"]].copy()
    datos = datos.rename(columns={
        "PAIS": "PAIS PRISIÓN",
        "SITUACION": "SITUACIÓN JURÍDICA",
        "GENERO": "GÉNERO",
        "EDAD": "GRUPO EDAD",
    })
    datos["CANTIDAD"] = pd.to_numeric(datos["CANTIDAD"], errors="coerce").fillna(0)

    def limpiar_pais(valor):
        reparado = reparar_mojibake(valor)
        clave = _etiqueta_clave_relacional(reparado)
        if clave in {"ESPA", "ESPAA", "ESPANA"}:
            return "España"
        return normalizar_pais(reparado)

    def limpiar_delito(valor):
        reparado = reparar_mojibake(valor)
        clave = _etiqueta_clave_relacional(reparado)
        if clave.startswith("NARCOTR") and clave.endswith("FICO"):
            return "Narcotráfico"
        return normalizar_delito(reparado)

    datos["PAIS PRISIÓN"] = datos["PAIS PRISIÓN"].map(limpiar_pais)
    datos["DELITO"] = datos["DELITO"].map(limpiar_delito)
    datos["SITUACIÓN JURÍDICA"] = datos["SITUACIÓN JURÍDICA"].map(normalizar_situacion)
    datos["GÉNERO"] = datos["GÉNERO"].map(normalizar_genero)
    datos["GRUPO EDAD"] = datos["GRUPO EDAD"].map(normalizar_edad)
    return datos


@app.route('/dimension-4')
def dimension_4():
    datos = datos_dimension_relacional()

    paises_seleccionados = request.args.getlist("pais")
    categorias_seleccionadas = request.args.getlist("categoria")
    delitos_seleccionados = [
        valor.removeprefix("DELITO::")
        for valor in categorias_seleccionadas
        if valor.startswith("DELITO::")
    ]
    situaciones_seleccionadas = [
        valor.removeprefix("SITUACION::")
        for valor in categorias_seleccionadas
        if valor.startswith("SITUACION::")
    ]

    filtrados = datos
    if paises_seleccionados:
        filtrados = filtrados.loc[filtrados["PAIS PRISIÓN"].isin(paises_seleccionados)]
    if delitos_seleccionados:
        filtrados = filtrados.loc[filtrados["DELITO"].isin(delitos_seleccionados)]
    if situaciones_seleccionadas:
        filtrados = filtrados.loc[
            filtrados["SITUACIÓN JURÍDICA"].isin(situaciones_seleccionadas)
        ]

    desconocidos = {"DESCONOCIDO", "SININFORMACION"}
    paises_conocidos = datos.loc[
        ~datos["PAIS PRISIÓN"].map(_etiqueta_clave_relacional).isin(desconocidos)
    ]
    total = float(filtrados["CANTIDAD"].sum())
    total_global = float(datos["CANTIDAD"].sum())
    ranking_paises = paises_conocidos.groupby("PAIS PRISIÓN")["CANTIDAD"].sum().sort_values(
        ascending=False
    )
    pais_principal = ranking_paises.index[0] if not ranking_paises.empty else "Sin información"
    cantidad_pais_principal = float(ranking_paises.iloc[0]) if not ranking_paises.empty else 0
    porcentaje_pais_principal = (
        cantidad_pais_principal / total_global * 100 if total_global else 0
    )
    ranking_delitos = filtrados.groupby("DELITO")["CANTIDAD"].sum().sort_values(
        ascending=False
    )
    delito_principal = ranking_delitos.index[0] if not ranking_delitos.empty else "Sin datos"
    cantidad_delito_principal = float(ranking_delitos.iloc[0]) if not ranking_delitos.empty else 0
    porcentaje_delito_principal = cantidad_delito_principal / total * 100 if total else 0

    def formato_numero(valor):
        return f"{valor:,.0f}".replace(",", ".")

    def preparar_figura(figura, altura=480):
        figura.update_layout(
            template="plotly_dark",
            height=altura,
            margin=dict(l=18, r=18, t=45, b=45),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend_title_text="",
            font=dict(family="Share Tech Mono, monospace"),
        )
        return figura

    graficas = []

    cruce = (
        filtrados.groupby(
            ["PAIS PRISIÓN", "DELITO", "SITUACIÓN JURÍDICA"], as_index=False
        )["CANTIDAD"].sum()
    )
    if not cruce.empty:
        total_pais_delito = cruce.groupby(
            ["PAIS PRISIÓN", "DELITO"]
        )["CANTIDAD"].transform("sum")
        condenados = cruce.assign(
            _CONDENADOS=cruce["SITUACIÓN JURÍDICA"].map(_etiqueta_clave_relacional).eq("CONDENADO")
            * cruce["CANTIDAD"]
        ).groupby(["PAIS PRISIÓN", "DELITO"])["_CONDENADOS"].transform("sum")
        cruce["Proporción de condenados (%)"] = (
            condenados.div(total_pais_delito.where(total_pais_delito.ne(0))).fillna(0) * 100
        )
        paises_top = (
            cruce.groupby("PAIS PRISIÓN")["CANTIDAD"].sum().nlargest(15).index
        )
        cruce = cruce.loc[cruce["PAIS PRISIÓN"].isin(paises_top)]
        figura = px.treemap(
            cruce,
            path=["PAIS PRISIÓN", "DELITO", "SITUACIÓN JURÍDICA"],
            values="CANTIDAD",
            color="Proporción de condenados (%)",
            color_continuous_scale="Blues",
            range_color=(0, 100),
            custom_data=["Proporción de condenados (%)"],
            labels={
                "PAIS PRISIÓN": "País",
                "SITUACIÓN JURÍDICA": "Situación jurídica",
                "CANTIDAD": "Personas",
            },
        )
        figura.update_traces(
            textinfo="label+value",
            hovertemplate=(
                "<b>%{label}</b><br>Personas: %{value:,.0f}"
                "<br>Condenados en país-delito: %{customdata[0]:.1f}%<extra></extra>"
            ),
        )
        preparar_figura(figura, 570)
        combinacion_top = cruce.nlargest(1, "CANTIDAD").iloc[0]
        interpretacion_1 = (
            f"Se muestran hasta 15 países. El área representa la cantidad agrupada "
            f"por país, delito y estado; el color indica la proporción de condenados "
            f"dentro de cada combinación país-delito. La mayor combinación visible "
            f"es {combinacion_top['PAIS PRISIÓN']} · {combinacion_top['DELITO']} · "
            f"{combinacion_top['SITUACIÓN JURÍDICA']} "
            f"({formato_numero(combinacion_top['CANTIDAD'])} personas)."
        )
        graficas.append(figura.to_html(full_html=False, include_plotlyjs="cdn"))
    else:
        interpretacion_1 = "No hay registros para los filtros seleccionados."
        graficas.append("")

    conocidos_filtrados = filtrados.loc[
        ~filtrados["PAIS PRISIÓN"].map(_etiqueta_clave_relacional).isin(desconocidos)
    ]
    if not conocidos_filtrados.empty:
        top_paises = (
            conocidos_filtrados.groupby("PAIS PRISIÓN")["CANTIDAD"].sum().nlargest(5).index
        )
        top_delitos = (
            conocidos_filtrados.groupby("DELITO")["CANTIDAD"].sum().nlargest(8).index
        )
        barras = conocidos_filtrados.loc[
            conocidos_filtrados["PAIS PRISIÓN"].isin(top_paises)
            & conocidos_filtrados["DELITO"].isin(top_delitos)
        ].groupby(
            ["PAIS PRISIÓN", "DELITO", "GÉNERO", "SITUACIÓN JURÍDICA"],
            as_index=False,
        )["CANTIDAD"].sum()
        figura = px.bar(
            barras,
            x="DELITO",
            y="CANTIDAD",
            color="SITUACIÓN JURÍDICA",
            facet_col="PAIS PRISIÓN",
            facet_col_wrap=3,
            facet_row="GÉNERO",
            barmode="stack",
            labels={
                "DELITO": "Delito",
                "CANTIDAD": "Personas",
                "SITUACIÓN JURÍDICA": "Situación jurídica",
            },
            hover_data={"GÉNERO": True, "PAIS PRISIÓN": True, "CANTIDAD": ":,.0f"},
        )
        figura.update_xaxes(tickangle=35)
        preparar_figura(figura, 740)
        top_combinacion = barras.groupby(
            ["PAIS PRISIÓN", "DELITO"]
        )["CANTIDAD"].sum().nlargest(1)
        pais_top, delito_top = top_combinacion.index[0]
        interpretacion_2 = (
            "Las barras apilan la situación jurídica y las facetas comparan género "
            "en los cinco países conocidos de mayor volumen. La combinación "
            f"país-delito más numerosa de la selección es {pais_top} · {delito_top} "
            f"({formato_numero(top_combinacion.iloc[0])} personas)."
        )
        graficas.append(figura.to_html(full_html=False, include_plotlyjs=False))
    else:
        interpretacion_2 = "No hay países identificados para comparar con los filtros actuales."
        graficas.append("")

    burbujas = (
        filtrados.groupby(["GRUPO EDAD", "DELITO", "GÉNERO"], as_index=False)["CANTIDAD"]
        .sum()
    )
    if not burbujas.empty:
        delitos_top_burbujas = (
            burbujas.groupby("DELITO")["CANTIDAD"].sum().nlargest(15).index
        )
        burbujas = burbujas.loc[burbujas["DELITO"].isin(delitos_top_burbujas)]
        figura = px.scatter(
            burbujas,
            x="DELITO",
            y="GRUPO EDAD",
            size="CANTIDAD",
            color="GÉNERO",
            size_max=42,
            hover_data={"GRUPO EDAD": True, "GÉNERO": True, "CANTIDAD": ":,.0f"},
            labels={
                "DELITO": "Delito",
                "GRUPO EDAD": "Grupo de edad",
                "GÉNERO": "Género",
                "CANTIDAD": "Personas",
            },
        )
        figura.update_xaxes(tickangle=35)
        preparar_figura(figura, 500)
        mayor_burbuja = burbujas.nlargest(1, "CANTIDAD").iloc[0]
        interpretacion_3 = (
            "Cada burbuja cruza grupo de edad, delito y género; su área representa "
            "la cantidad. Se muestran los 15 delitos más frecuentes. La combinación "
            f"mayor es {mayor_burbuja['GRUPO EDAD']} · {mayor_burbuja['DELITO']} · "
            f"{mayor_burbuja['GÉNERO']} "
            f"({formato_numero(mayor_burbuja['CANTIDAD'])} personas)."
        )
        graficas.append(figura.to_html(full_html=False, include_plotlyjs=False))
    else:
        interpretacion_3 = "No hay registros para los filtros seleccionados."
        graficas.append("")

    narcotrafico = paises_conocidos.loc[
        paises_conocidos["DELITO"].map(_etiqueta_clave_relacional).eq("NARCOTRAFICO")
    ]
    if paises_seleccionados:
        narcotrafico = narcotrafico.loc[
            narcotrafico["PAIS PRISIÓN"].isin(paises_seleccionados)
        ]
    grafica_narcotrafico = ""
    tabla_narcotrafico = []
    if not narcotrafico.empty:
        principales = (
            narcotrafico.groupby("PAIS PRISIÓN")["CANTIDAD"].sum().nlargest(10).index
        )
        narcotrafico = narcotrafico.loc[narcotrafico["PAIS PRISIÓN"].isin(principales)]
        tabla = narcotrafico.groupby(
            ["PAIS PRISIÓN", "SITUACIÓN JURÍDICA"], as_index=False
        )["CANTIDAD"].sum()
        totales = tabla.groupby("PAIS PRISIÓN")["CANTIDAD"].transform("sum")
        tabla["Proporción (%)"] = tabla["CANTIDAD"].div(totales).mul(100)
        figura = px.bar(
            tabla,
            x="PAIS PRISIÓN",
            y="Proporción (%)",
            color="SITUACIÓN JURÍDICA",
            barmode="stack",
            hover_data={"CANTIDAD": ":,.0f", "Proporción (%)": ":.1f"},
            labels={
                "PAIS PRISIÓN": "País",
                "Proporción (%)": "Proporción en el país (%)",
                "SITUACIÓN JURÍDICA": "Situación jurídica",
            },
        )
        figura.update_xaxes(tickangle=35)
        preparar_figura(figura, 410)
        grafica_narcotrafico = figura.to_html(full_html=False, include_plotlyjs=False)
        tabla_narcotrafico = tabla.sort_values(
            ["PAIS PRISIÓN", "CANTIDAD"], ascending=[True, False]
        ).to_dict("records")

    generos = paises_conocidos
    if paises_seleccionados:
        generos = generos.loc[generos["PAIS PRISIÓN"].isin(paises_seleccionados)]
    agrupado_genero = generos.groupby(
        ["GÉNERO", "PAIS PRISIÓN", "DELITO"], as_index=False
    )["CANTIDAD"].sum()
    if not agrupado_genero.empty:
        figura = px.treemap(
            agrupado_genero,
            path=["GÉNERO", "PAIS PRISIÓN", "DELITO"],
            values="CANTIDAD",
            color="CANTIDAD",
            color_continuous_scale="Teal",
            labels={
                "GÉNERO": "Género",
                "PAIS PRISIÓN": "País",
                "DELITO": "Delito",
                "CANTIDAD": "Personas",
            },
        )
        figura.update_traces(
            hovertemplate="<b>%{label}</b><br>Personas: %{value:,.0f}<extra></extra>"
        )
        preparar_figura(figura, 430)
        grafica_genero = figura.to_html(full_html=False, include_plotlyjs=False)
    else:
        grafica_genero = ""

    crimen_totales = datos.groupby("DELITO")["CANTIDAD"].sum()
    crimenes_genericos = {"DESCONOCIDO", "SININFORMACION", "OTROS"}
    crimenes_especificos = crimen_totales.loc[
        ~crimen_totales.index.map(_etiqueta_clave_relacional).isin(crimenes_genericos)
    ]
    delitos_raros = crimenes_especificos.nsmallest(5).index
    raros = paises_conocidos.loc[paises_conocidos["DELITO"].isin(delitos_raros)]
    raros_agrupados = raros.groupby(
        ["PAIS PRISIÓN", "DELITO", "SITUACIÓN JURÍDICA"], as_index=False
    )["CANTIDAD"].sum()
    if not raros_agrupados.empty:
        paises_raros_top = (
            raros_agrupados.groupby("PAIS PRISIÓN")["CANTIDAD"].sum().nlargest(20).index
        )
        raros_agrupados = raros_agrupados.loc[
            raros_agrupados["PAIS PRISIÓN"].isin(paises_raros_top)
        ]
        figura = px.scatter(
            raros_agrupados,
            x="PAIS PRISIÓN",
            y="DELITO",
            size="CANTIDAD",
            color="SITUACIÓN JURÍDICA",
            size_max=36,
            hover_data={"CANTIDAD": ":,.0f"},
            labels={
                "PAIS PRISIÓN": "País",
                "DELITO": "Delito de baja frecuencia",
                "SITUACIÓN JURÍDICA": "Situación jurídica",
                "CANTIDAD": "Personas",
            },
        )
        figura.update_xaxes(tickangle=35)
        preparar_figura(figura, 400)
        grafica_raros = figura.to_html(full_html=False, include_plotlyjs=False)
        tabla_raros = raros_agrupados.nlargest(25, "CANTIDAD").to_dict("records")
    else:
        grafica_raros = ""
        tabla_raros = []

    paises_decision = (
        datos.loc[datos["PAIS PRISIÓN"].isin(paises_seleccionados)]
        if paises_seleccionados
        else datos
    )
    paises_decision = paises_decision.loc[
        ~paises_decision["PAIS PRISIÓN"].map(_etiqueta_clave_relacional).isin(desconocidos)
    ]
    sin_definicion = paises_decision.loc[
        paises_decision["SITUACIÓN JURÍDICA"].map(_etiqueta_clave_relacional).isin(
            {"ENJUICIO", "ENINVESTIGACION"}
        )
    ].groupby("PAIS PRISIÓN")["CANTIDAD"].sum().rename("Personas sin definición")
    totales_decision = paises_decision.groupby("PAIS PRISIÓN")["CANTIDAD"].sum().rename(
        "Total conocido"
    )
    prioridades = pd.concat([sin_definicion, totales_decision], axis=1).fillna(0)
    prioridades["Proporción sin definición (%)"] = (
        prioridades["Personas sin definición"]
        .div(prioridades["Total conocido"].where(prioridades["Total conocido"].ne(0)))
        .fillna(0)
        * 100
    )
    prioridades = prioridades.sort_values(
        ["Proporción sin definición (%)", "Personas sin definición"],
        ascending=False,
    ).head(5).reset_index()

    variables = [
        ("PAIS PRISIÓN", "Cualitativa nominal", "Territorio"),
        ("DELITO", "Cualitativa nominal", "Causa o tipología"),
        ("SITUACIÓN JURÍDICA", "Cualitativa nominal/ordinal", "Estado del proceso"),
        ("GÉNERO", "Cualitativa nominal", "Variable demográfica"),
        ("GRUPO EDAD", "Cualitativa ordinal", "Etapa de vida"),
        ("CANTIDAD", "Cuantitativa discreta", "Métrica de conteo"),
    ]

    return render_template(
        "dim_4.html",
        titulo="Dimensión 4",
        variables=variables,
        paises=sorted(datos["PAIS PRISIÓN"].dropna().unique()),
        delitos=sorted(datos["DELITO"].dropna().unique()),
        situaciones=sorted(datos["SITUACIÓN JURÍDICA"].dropna().unique()),
        paises_seleccionados=paises_seleccionados,
        categorias_seleccionadas=categorias_seleccionadas,
        total=formato_numero(total),
        pais_principal=pais_principal,
        porcentaje_pais_principal=porcentaje_pais_principal,
        delito_principal=delito_principal,
        porcentaje_delito_principal=porcentaje_delito_principal,
        graficas=graficas,
        interpretaciones=[interpretacion_1, interpretacion_2, interpretacion_3],
        grafica_narcotrafico=grafica_narcotrafico,
        tabla_narcotrafico=tabla_narcotrafico,
        grafica_genero=grafica_genero,
        grafica_raros=grafica_raros,
        tabla_raros=tabla_raros,
        prioridades=prioridades.to_dict("records"),
    )


@app.route('/analisis-relacional')
def analisis_relacional():
    datos = datos_dimension_relacional()

    total = float(datos["CANTIDAD"].sum())
    desconocidos = {"DESCONOCIDO", "SININFORMACION"}
    conocidos = datos.loc[
        ~datos["PAIS PRISIÓN"].map(_etiqueta_clave_relacional).isin(desconocidos)
    ]
    cantidad_paises_conocidos = float(conocidos["CANTIDAD"].sum())
    paises = conocidos.groupby("PAIS PRISIÓN")["CANTIDAD"].sum().sort_values(
        ascending=False
    )
    pais_principal = paises.index[0] if not paises.empty else "Sin información"
    cantidad_pais_principal = float(paises.iloc[0]) if not paises.empty else 0
    porcentaje_pais_principal = cantidad_pais_principal / total * 100 if total else 0

    delitos = datos.groupby("DELITO")["CANTIDAD"].sum().sort_values(ascending=False)
    delito_principal = delitos.index[0] if not delitos.empty else "Sin información"
    cantidad_delito_principal = float(delitos.iloc[0]) if not delitos.empty else 0
    porcentaje_delito_principal = cantidad_delito_principal / total * 100 if total else 0

    sin_definicion = datos.loc[
        datos["SITUACIÓN JURÍDICA"].map(_etiqueta_clave_relacional).isin(
            {"ENJUICIO", "ENINVESTIGACION"}
        ),
        "CANTIDAD",
    ].sum()
    porcentaje_sin_definicion = float(sin_definicion) / total * 100 if total else 0

    def resumen_variable(columna):
        resumen = (
            datos.groupby(columna, dropna=False)["CANTIDAD"]
            .sum()
            .sort_values(ascending=False)
        )
        return [
            {
                "categoria": str(categoria),
                "cantidad": float(cantidad),
                "porcentaje": float(cantidad / total * 100) if total else 0,
            }
            for categoria, cantidad in resumen.items()
        ]

    resumenes_variables = [
        {
            "titulo": "PAÍS DE PRISIÓN",
            "nombre": "PAIS PRISIÓN",
            "filas": resumen_variable("PAIS PRISIÓN"),
            "nota": (
                "El país desconocido se conserva como categoría: excluirlo "
                "del total ocultaría una limitación importante de cobertura."
            ),
        },
        {
            "titulo": "DELITO",
            "nombre": "DELITO",
            "filas": resumen_variable("DELITO"),
            "nota": "Las categorías describen el delito reportado y no prueban por sí solas sus causas.",
        },
        {
            "titulo": "SITUACIÓN JURÍDICA",
            "nombre": "SITUACIÓN JURÍDICA",
            "filas": resumen_variable("SITUACIÓN JURÍDICA"),
            "nota": (
                "“En juicio” y “En investigación” se agrupan como casos sin "
                "definición jurídica únicamente para el indicador de seguimiento."
            ),
        },
        {
            "titulo": "GÉNERO",
            "nombre": "GÉNERO",
            "filas": resumen_variable("GÉNERO"),
            "nota": "La categoría reportada no describe por sí sola identidad ni circunstancias individuales.",
        },
        {
            "titulo": "GRUPO DE EDAD",
            "nombre": "GRUPO EDAD",
            "filas": resumen_variable("GRUPO EDAD"),
            "nota": "“Sin información” se mantiene visible y no se redistribuye entre los grupos conocidos.",
        },
    ]

    paises_desconocidos = datos.loc[
        datos["PAIS PRISIÓN"].map(_etiqueta_clave_relacional).isin(desconocidos),
        "CANTIDAD",
    ].sum()
    porcentaje_pais_desconocido = (
        float(paises_desconocidos) / total * 100 if total else 0
    )

    narcotrafico = datos.loc[
        datos["DELITO"].map(_etiqueta_clave_relacional).eq("NARCOTRAFICO")
    ]
    total_narcotrafico = float(narcotrafico["CANTIDAD"].sum())
    narcotrafico_condenado = float(
        narcotrafico.loc[
            narcotrafico["SITUACIÓN JURÍDICA"]
            .map(_etiqueta_clave_relacional)
            .eq("CONDENADO"),
            "CANTIDAD",
        ].sum()
    )
    porcentaje_narcotrafico_condenado = (
        narcotrafico_condenado / total_narcotrafico * 100
        if total_narcotrafico else 0
    )

    mayor_cruce_juridico = (
        datos.groupby(["DELITO", "SITUACIÓN JURÍDICA"])["CANTIDAD"]
        .sum()
        .sort_values(ascending=False)
    )
    if mayor_cruce_juridico.empty:
        delito_estado_principal = "Sin datos"
        situacion_delito_principal = "Sin datos"
        cantidad_delito_estado_principal = 0.0
    else:
        (delito_estado_principal, situacion_delito_principal) = mayor_cruce_juridico.index[0]
        cantidad_delito_estado_principal = float(mayor_cruce_juridico.iloc[0])

    def preparar_figura(figura, altura=470):
        figura.update_layout(
            template="plotly_dark",
            height=altura,
            margin=dict(l=18, r=18, t=45, b=45),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend_title_text="",
            font=dict(family="Share Tech Mono, monospace"),
        )
        return figura

    graficas = []
    interpretaciones = []

    cruce = (
        conocidos.groupby(
            ["PAIS PRISIÓN", "DELITO", "SITUACIÓN JURÍDICA"], as_index=False
        )["CANTIDAD"].sum()
    )
    if not cruce.empty:
        paises_top = paises.head(15).index
        cruce = cruce.loc[cruce["PAIS PRISIÓN"].isin(paises_top)]
        figura = px.treemap(
            cruce,
            path=["PAIS PRISIÓN", "DELITO", "SITUACIÓN JURÍDICA"],
            values="CANTIDAD",
            color="CANTIDAD",
            color_continuous_scale="Blues",
            labels={
                "PAIS PRISIÓN": "País",
                "SITUACIÓN JURÍDICA": "Situación jurídica",
                "CANTIDAD": "Personas reportadas",
            },
        )
        figura.update_traces(
            textinfo="label+value",
            hovertemplate="<b>%{label}</b><br>Personas reportadas: %{value:,.0f}<extra></extra>",
        )
        preparar_figura(figura, 550)
        graficas.append(figura.to_html(full_html=False, include_plotlyjs="cdn"))
        interpretaciones.append(
            f"Entre los países identificados, {pais_principal} reúne "
            f"{cantidad_pais_principal:,.0f} personas reportadas "
            f"({porcentaje_pais_principal:.1f}% del total, incluidas las "
            "categorías sin país identificado). El treemap muestra cómo se "
            "distribuye cada país entre delitos y situaciones jurídicas."
        )
    else:
        graficas.append("")
        interpretaciones.append("No hay registros con país identificado para comparar.")

    paises_top = paises.head(5).index
    delitos_top = delitos.head(8).index
    barras = conocidos.loc[
        conocidos["PAIS PRISIÓN"].isin(paises_top)
        & conocidos["DELITO"].isin(delitos_top)
    ].groupby(
        ["PAIS PRISIÓN", "DELITO", "GÉNERO", "SITUACIÓN JURÍDICA"],
        as_index=False,
    )["CANTIDAD"].sum()
    if not barras.empty:
        figura = px.bar(
            barras,
            x="DELITO",
            y="CANTIDAD",
            color="SITUACIÓN JURÍDICA",
            facet_col="PAIS PRISIÓN",
            facet_col_wrap=3,
            facet_row="GÉNERO",
            barmode="stack",
            labels={
                "DELITO": "Delito",
                "CANTIDAD": "Personas reportadas",
                "SITUACIÓN JURÍDICA": "Situación jurídica",
            },
        )
        figura.update_xaxes(tickangle=35)
        preparar_figura(figura, 740)
        graficas.append(figura.to_html(full_html=False, include_plotlyjs=False))
        interpretaciones.append(
            "La comparación se limita a los cinco países y ocho delitos con "
            "mayor volumen conocido; las barras apilan la situación jurídica "
            "y separan los grupos por género. La visualización describe "
            "volúmenes, no tasas de riesgo ni diferencias causales."
        )
    else:
        graficas.append("")
        interpretaciones.append("No hay combinaciones identificables para esta comparación.")

    burbujas = datos.groupby(
        ["GRUPO EDAD", "DELITO", "GÉNERO"], as_index=False
    )["CANTIDAD"].sum()
    if not burbujas.empty:
        delitos_burbuja = (
            burbujas.groupby("DELITO")["CANTIDAD"].sum().nlargest(15).index
        )
        burbujas = burbujas.loc[burbujas["DELITO"].isin(delitos_burbuja)]
        figura = px.scatter(
            burbujas,
            x="DELITO",
            y="GRUPO EDAD",
            size="CANTIDAD",
            color="GÉNERO",
            size_max=42,
            hover_data={"GRUPO EDAD": True, "GÉNERO": True, "CANTIDAD": ":,.0f"},
            labels={
                "DELITO": "Delito",
                "GRUPO EDAD": "Grupo de edad",
                "GÉNERO": "Género",
                "CANTIDAD": "Personas reportadas",
            },
        )
        figura.update_xaxes(tickangle=35)
        preparar_figura(figura, 500)
        mayor_burbuja = burbujas.nlargest(1, "CANTIDAD").iloc[0]
        graficas.append(figura.to_html(full_html=False, include_plotlyjs=False))
        interpretaciones.append(
            f"Cada burbuja cruza edad, delito y género; el tamaño refleja "
            f"personas reportadas. La combinación de mayor volumen visible es "
            f"{mayor_burbuja['GRUPO EDAD']} · {mayor_burbuja['DELITO']} · "
            f"{mayor_burbuja['GÉNERO']} "
            f"({mayor_burbuja['CANTIDAD']:,.0f} personas reportadas)."
        )
    else:
        graficas.append("")
        interpretaciones.append("No hay combinaciones de edad, delito y género para visualizar.")

    variables = [
        ("PAIS PRISIÓN", "Cualitativa nominal", "Territorio donde se reporta la detención."),
        ("DELITO", "Cualitativa nominal", "Causa o tipología asociada al registro."),
        ("SITUACIÓN JURÍDICA", "Cualitativa nominal/ordinal", "Estado del proceso reportado."),
        ("GÉNERO", "Cualitativa nominal", "Característica demográfica registrada."),
        ("GRUPO EDAD", "Cualitativa ordinal", "Grupo etario registrado."),
        ("CANTIDAD", "Cuantitativa discreta", "Número reportado en cada registro."),
    ]

    return render_template(
        "analisis_relacional.html",
        total=total,
        total_registros=len(datos),
        cantidad_paises_conocidos=cantidad_paises_conocidos,
        porcentaje_paises_conocidos=(
            cantidad_paises_conocidos / total * 100 if total else 0
        ),
        pais_principal=pais_principal,
        porcentaje_pais_principal=porcentaje_pais_principal,
        cantidad_pais_principal=cantidad_pais_principal,
        porcentaje_pais_desconocido=porcentaje_pais_desconocido,
        delito_principal=delito_principal,
        cantidad_delito_principal=cantidad_delito_principal,
        porcentaje_delito_principal=porcentaje_delito_principal,
        porcentaje_sin_definicion=porcentaje_sin_definicion,
        cantidad_sin_definicion=float(sin_definicion),
        resumenes_variables=resumenes_variables,
        total_narcotrafico=total_narcotrafico,
        narcotrafico_condenado=narcotrafico_condenado,
        porcentaje_narcotrafico_condenado=porcentaje_narcotrafico_condenado,
        delito_estado_principal=delito_estado_principal,
        situacion_delito_principal=situacion_delito_principal,
        cantidad_delito_estado_principal=cantidad_delito_estado_principal,
        variables=variables,
        graficas=graficas,
        interpretaciones=interpretaciones,
    )


# ============================================================
# SALUD DEL SERVICIO
# ------------------------------------------------------------
# Es la ruta que usa la persona responsable de la publicación para
# confirmar, contra la URL ya desplegada, que el proceso está vivo y
# que el conjunto de datos viaja en la imagen. Sin esto, un despliegue
# que arranca pero no encuentra el CSV solo se detecta cuando alguien
# abre el tablero en la revisión.
#
# Por defecto es barata: solo mira el archivo en disco. Con
# /health?carga=1 además lee el CSV y construye la serie temporal,
# que es el cálculo real de todas las páginas.
# ============================================================

@app.route('/health')
def health():

    inicio = pd.Timestamp.now()

    archivo = {
        "ruta_relativa": os.path.relpath(DATA_PATH, BASE_DIR),
        "presente": os.path.exists(DATA_PATH),
        "bytes": os.path.getsize(DATA_PATH) if os.path.exists(DATA_PATH) else 0,
    }

    # Si el dataset ya está en caché, el proceso lo tiene cargado y no
    # hay nada que recalcular.
    archivo["en_cache"] = "df" in _CACHE_DATASET

    estado = {
        "servicio": "ok",
        "version_app": "1.0.0",
        "dataset": archivo,
        "comprobado": "archivo",
    }

    if request.args.get("carga") == "1":
        try:
            df_minimo = temporal.cargar_datos(solo_minimas=True)
            serie = temporal.serie_temporal(df_minimo)
            estado["comprobado"] = "carga_completa"
            estado["dataset"]["registros_csv"] = int(df_minimo.shape[0])
            estado["dataset"]["cortes"] = int(len(serie))
        except Exception as error:
            estado["servicio"] = "error"
            estado["error"] = f"{type(error).__name__}: {error}"

    if not archivo["presente"]:
        estado["servicio"] = "error"
        estado["error"] = "El conjunto de datos no está en la imagen"

    estado["duracion_ms"] = int(
        (pd.Timestamp.now() - inicio).total_seconds() * 1000
    )

    return jsonify(estado), (200 if estado["servicio"] == "ok" else 503)


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
# DIMENSIÓN TERRITORIAL
# ------------------------------------------------------------
# La lógica (normalización de países, continentes, consulados y
# gráficas) está en src/dimension_territorial.py. Se reutiliza el
# dataset ya procesado y cacheado, igual que en las otras dimensiones.
# ============================================================

@app.route('/dimension-territorial')
def dimension_territorial():

    contexto = territorial.construir_contexto_territorial(
        cargar_dataset_procesado(),
        continente=request.args.get("continente", "").strip(),
        delito=request.args.get("delito", "").strip(),
    )

    return render_template(
        'dim_2.html',
        titulo="Dimensión Territorial",
        **contexto,
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
    # 1. FILTRO TEMPORAL (RANGO DE AÑOS)
    # --------------------------------------------------------

    # La dimensión temporal se filtra por años, que es su propia
    # variable. No filtra por país ni por situación jurídica: esos
    # cortes pertenecen a la dimensión poblacional y aquí solo
    # añadirían subconjuntos sin aportar nada a la lectura de la
    # evolución. Se reutiliza la capa de datos ya normalizada, así el
    # costo de leer el CSV se paga una sola vez por proceso.
    df_base = cargar_dataset_procesado()

    serie_completa = temporal.serie_temporal(df_base)
    anios = temporal.anios_disponibles(serie_completa)

    anio_min = anios[0]
    anio_max = anios[-1]

    anio_desde = anio_en_rango(
        request.args.get("anio_desde"), anio_min, anio_max, anio_min
    )
    anio_hasta = anio_en_rango(
        request.args.get("anio_hasta"), anio_min, anio_max, anio_max
    )

    if anio_desde > anio_hasta:
        anio_desde, anio_hasta = anio_hasta, anio_desde

    # --------------------------------------------------------
    # 2. SERIE DE CORTES Y EVOLUCIÓN
    # --------------------------------------------------------

    serie = temporal.recortar_por_anio(
        serie_completa, anio_desde, anio_hasta
    )
    indicadores = temporal.indicadores(serie)
    anual = temporal.resumen_por_anio(serie)
    por_mes = temporal.variacion_por_mes_del_ano(serie)

    # El rango de años siempre cae dentro de los años con cortes, pero
    # se conserva la salida por si el conjunto llegara vacío: en ese
    # caso no se construyen las gráficas y se devuelve el aviso.
    sin_datos = serie.empty

    if sin_datos:
        return render_template(
            'dim_3.html',
            titulo="Dimensión Temporal",
            sin_datos=True,
            anios=anios,
            anio_min=anio_min,
            anio_max=anio_max,
            anio_desde=anio_desde,
            anio_hasta=anio_hasta,
        )

    # --------------------------------------------------------
    # 3. GRÁFICA 1 — STOCK POR CORTE
    # --------------------------------------------------------

    # Una sola serie, sin desglose por tipo de corte: la línea continua
    # del stock es lo que el tablero muestra y nada más.
    fig_stock = px.line(
        serie,
        x="FECHA",
        y="stock",
        markers=True,
        labels={
            "FECHA": "Fecha de corte",
            "stock": "Personas detenidas",
        },
    )

    fig_stock.update_traces(
        line=dict(width=2, color="#00f0ff"),
        marker=dict(size=6, color="#00f0ff"),
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
        showlegend=False,
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

    # El texto sitúa el rango elegido. Cuando abarca todo el periodo no
    # se habla de filtro, porque es la lectura por defecto del tablero.
    if anio_desde == anio_min and anio_hasta == anio_max:
        texto_contexto = "En todo el periodo"
    elif anio_desde == anio_hasta:
        texto_contexto = f"En el año <em>{anio_desde}</em>"
    else:
        texto_contexto = (
            f"En el periodo <em>{anio_desde}–{anio_hasta}</em>"
        )

    # El máximo de la serie se describe de forma factual: fecha y valor.
    # No se atribuye a ninguna causa, porque el conjunto no trae
    # información que permita explicarlo.
    fila_maximo = serie.loc[serie["stock"].idxmax()]

    interp_stock = (
        f"{texto_contexto}, el stock de detenidos va de "
        f"<strong>{indicadores['stock_inicial']:,}</strong> personas el "
        f"{indicadores['fecha_stock_inicial']} a "
        f"<strong>{indicadores['stock_actual']:,}</strong> el "
        f"{indicadores['fecha_stock_actual']}, un "
        f"<strong>{indicadores['crecimiento_total_pct']:+.2f}%</strong> en todo "
        f"el periodo. El valor más alto de la serie es de "
        f"<strong>{int(fila_maximo['stock']):,}</strong> personas el "
        f"{fila_maximo['FECHA'].date().isoformat()}, y el más bajo de "
        f"<strong>{int(serie['stock'].min()):,}</strong>."
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
    # 7. DATOS DE LAS TABLAS Y DEL CALENDARIO DE CORTE
    # --------------------------------------------------------

    filas_anuales = [
        {
            "anio": int(fila["anio"]),
            "cortes": int(fila["cortes"]),
            "stock_cierre": int(fila["stock_cierre"]),
            "crecimiento_neto": int(fila["crecimiento_neto"]),
            "crecimiento_pct": float(fila["crecimiento_pct"]),
            "personas_por_registro": float(fila["personas_por_registro"]),
            "registros_min": int(fila["registros_min"]),
            "registros_cierre": int(fila["registros_cierre"]),
        }
        for _, fila in anual.iterrows()
    ]

    # El calendario de publicación es irregular: no hay un corte por mes.
    # Se mide para poder decirlo con cifras en lugar de afirmarlo.
    calendario = temporal.calendario_de_cortes(serie)

    # El texto de las conclusiones en prosa necesita el tamaño del
    # periodo en palabras; se calcula para no dejar la cifra fija.
    anios_periodo_texto = en_palabras(
        temporal.duracion_en_anos(serie), " años"
    )

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
        stock_inicial=indicadores["stock_inicial"],
        fecha_stock_inicial=indicadores["fecha_stock_inicial"],
        anios_periodo_texto=anios_periodo_texto,

        grafica_stock=grafica_stock,
        grafica_variacion=grafica_variacion,
        grafica_anual=grafica_anual,

        interp_stock=interp_stock,
        interp_variacion=interp_variacion,
        interp_anual=interp_anual,

        calendario=calendario,
        filas_anuales=filas_anuales,
        filas_mes=filas_mes,

        anios=anios,
        anio_min=anio_min,
        anio_max=anio_max,
        anio_desde=anio_desde,
        anio_hasta=anio_hasta,
    )


# ============================================================
# ANÁLISIS TEMPORAL — CONOCIMIENTOS EVIDENTES
# ------------------------------------------------------------
# Esta página no acepta filtros: documenta los tres conocimientos
# evidentes de la dimensión sobre la serie completa, que es la única
# lectura que sostiene el resto del análisis.
# ============================================================

@app.route('/analisis-temporal')
def analisis_temporal():

    # --------------------------------------------------------
    # 1. SERIE COMPLETA
    # --------------------------------------------------------

    serie = temporal.serie_temporal(cargar_dataset_procesado())
    indicadores = temporal.indicadores(serie)
    anual = temporal.resumen_por_anio(serie)
    por_mes = temporal.variacion_por_mes_del_ano(serie)

    comparables = serie[serie["variacion_neta"].notna()].copy()
    sube = int((comparables["variacion_neta"] > 0).sum())
    baja = int(len(comparables) - sube)

    # --------------------------------------------------------
    # 2. GRÁFICA K1 — STOCK POR CORTE
    # --------------------------------------------------------

    # Una sola serie también en la página de análisis: la línea del
    # stock, continua, sin marcar ningún corte.
    fig_k1 = px.line(
        serie,
        x="FECHA",
        y="stock",
        markers=True,
        labels={
            "FECHA": "Fecha de corte",
            "stock": "Personas detenidas",
        },
    )

    fig_k1.update_traces(
        line=dict(width=2, color="#00f0ff"),
        marker=dict(size=5, color="#00f0ff"),
        hovertemplate=(
            "<b>%{x|%d/%m/%Y}</b><br>"
            "Stock: %{y:,.0f} personas<extra></extra>"
        ),
    )

    fig_k1.update_layout(
        template="plotly_dark",
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=30, b=10),
        font=dict(family="Share Tech Mono, monospace", size=11),
        showlegend=False,
        xaxis=dict(gridcolor="rgba(0,240,255,0.08)"),
        yaxis=dict(gridcolor="rgba(0,240,255,0.08)"),
    )

    grafica_k1 = fig_k1.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        config={"displayModeBar": False},
    )

    # --------------------------------------------------------
    # 3. GRÁFICA K2 — VARIACIÓN NETA
    # --------------------------------------------------------

    comparables["MOVIMIENTO"] = np.where(
        comparables["variacion_neta"] >= 0,
        "Aumento",
        "Disminucion",
    )

    fig_k2 = px.bar(
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

    fig_k2.add_hline(
        y=0, line_width=1, line_dash="dot", line_color="rgba(255,255,255,0.35)"
    )

    fig_k2.update_traces(
        hovertemplate=(
            "<b>%{x|%d/%m/%Y}</b><br>"
            "Variacion: %{y:+,.0f} personas<extra></extra>"
        ),
    )

    fig_k2.update_layout(
        template="plotly_dark",
        height=340,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=30, b=10),
        font=dict(family="Share Tech Mono, monospace", size=11),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis=dict(gridcolor="rgba(0,240,255,0.08)"),
        yaxis=dict(gridcolor="rgba(0,240,255,0.08)"),
    )

    grafica_k2 = fig_k2.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": False},
    )

    # --------------------------------------------------------
    # 4. GRÁFICA K3 — CRECIMIENTO NETO POR AÑO
    # --------------------------------------------------------

    fig_k3 = px.bar(
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

    fig_k3.add_hline(
        y=0, line_width=1, line_dash="dot", line_color="rgba(255,255,255,0.35)"
    )

    fig_k3.update_layout(
        template="plotly_dark",
        height=380,
        coloraxis_showscale=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=30, b=10),
        font=dict(family="Share Tech Mono, monospace", size=11),
        xaxis=dict(gridcolor="rgba(0,240,255,0.08)"),
        yaxis=dict(gridcolor="rgba(0,240,255,0.08)"),
    )

    grafica_k3 = fig_k3.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": False},
    )

    # --------------------------------------------------------
    # 5. DATOS DERIVADOS PARA LA PLANTILLA
    # --------------------------------------------------------

    filas_anuales = [
        {
            "anio": int(fila["anio"]),
            "cortes": int(fila["cortes"]),
            "stock_cierre": int(fila["stock_cierre"]),
            "crecimiento_neto": int(fila["crecimiento_neto"]),
            "crecimiento_pct": float(fila["crecimiento_pct"]),
            "personas_por_registro": float(fila["personas_por_registro"]),
            "registros_min": int(fila["registros_min"]),
            "registros_cierre": int(fila["registros_cierre"]),
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

    # ------------------------------------------------------------
    # 5.1. AÑOS CITADOS EN LAS CONCLUSIONES
    # ------------------------------------------------------------
    # El texto de los conocimientos menciona el tamaño del periodo, el
    # calendario de publicación y la fragmentación de los registros. Todo
    # eso se deriva aquí para que ninguna cifra quede escrita a mano en
    # el HTML.

    anios_periodo = temporal.duracion_en_anos(serie)
    anios_periodo_texto = en_palabras(anios_periodo, " años")

    calendario = temporal.calendario_de_cortes(serie)

    # Fragmentación: se compara el año en que la fuente más agrupó
    # personas por registro contra el último año de la serie. Se usa el
    # mínimo de registros del año agrupado, no su cierre, para que un
    # corte atypico no contamine la comparación.
    fragmentacion = None

    if not anual.empty:
        anio_pico = anual.loc[anual["personas_por_registro"].idxmax()]
        anio_cierre = anual.iloc[-1]

        registros_antes = int(anio_pico["registros_min"])
        registros_despues = int(anio_cierre["registros_cierre"])

        fragmentacion = {
            "anio_pico": int(anio_pico["anio"]),
            "anio_cierre": int(anio_cierre["anio"]),
            "personas_por_registro_antes": float(
                anio_pico["personas_por_registro"]
            ),
            "personas_por_registro_despues": float(
                anio_cierre["personas_por_registro"]
            ),
            "registros_antes": registros_antes,
            "registros_despues": registros_despues,
            "crecimiento_registros_pct": round(
                (registros_despues / registros_antes - 1) * 100, 1
            ) if registros_antes else 0.0,
        }

    # Años con más y con menos cortes publicados. La diferencia entre
    # ambos es la que impide comparar dos años como si tuvieran la
    # misma densidad de observación.
    anio_mas_cortes = max(
        filas_anuales,
        key=lambda f: f["cortes"],
        default=None,
    )

    anio_menos_cortes = min(
        filas_anuales,
        key=lambda f: f["cortes"],
        default=None,
    )

    # Cuánto mayor es el máximo de la serie que el corte final. Sirve
    # para mostrar que un presupuesto calculado sobre el pico serait
    # innecesario.
    stock_maximo = int(serie["stock"].max())
    stock_maximo_sobre_media_pct = round(
        (stock_maximo / indicadores["stock_actual"] - 1) * 100
    ) if indicadores["stock_actual"] else 0

    # Peso del movimiento más grande de la serie sobre el stock actual.
    # Sirve para afirmar si los extremos temporales son relevantes o
    # marginales sin escribir una magnitud fija en la prosa.
    extremos = [
        indicadores["periodo_mayor_aumento"],
        indicadores["periodo_mayor_disminucion"],
    ]

    movimiento_maximo = max(
        (abs(p["variacion"]) for p in extremos if p),
        default=0,
    )

    movimiento_maximo_pct = round(
        movimiento_maximo / indicadores["stock_actual"] * 100, 1
    ) if indicadores["stock_actual"] else 0.0

    # --------------------------------------------------------
    # 6. RENDER
    # --------------------------------------------------------

    return render_template(
        'analisis_temporal.html',

        total_cortes=indicadores["total_cortes"],
        cortes_comparables=indicadores["cortes_comparables"],
        fecha_inicial=indicadores["fecha_stock_inicial"],
        fecha_final=indicadores["fecha_stock_actual"],

        stock_inicial=indicadores["stock_inicial"],
        stock_actual=indicadores["stock_actual"],
        stock_maximo=int(serie["stock"].max()),
        stock_maximo_sobre_media_pct=stock_maximo_sobre_media_pct,
        crecimiento_total_pct=indicadores["crecimiento_total_pct"],
        ritmo_diario=indicadores["ritmo_diario"],

        anios_periodo=anios_periodo,
        anios_periodo_texto=anios_periodo_texto,

        sube=sube,
        baja=baja,

        periodo_mayor_aumento=indicadores["periodo_mayor_aumento"],
        periodo_mayor_disminucion=indicadores["periodo_mayor_disminucion"],

        fragmentacion=fragmentacion,
        calendario=calendario,
        anio_mas_cortes=anio_mas_cortes,
        anio_menos_cortes=anio_menos_cortes,
        movimiento_maximo_pct=movimiento_maximo_pct,

        grafica_k1=grafica_k1,
        grafica_k2=grafica_k2,
        grafica_k3=grafica_k3,

        filas_anuales=filas_anuales,
        filas_mes=filas_mes,
    )


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == '__main__':
    # `use_reloader=False` a proposito: el dataset pesa 54 MB y tarda cerca
    # de un segundo en leerse y normalizarse. Con el recargador automatico
    # cada guardado de archivo vuelve a cargar todo el dataset, y ademas el
    # proceso padre y el hijo terminarian cargando dos copias a la vez.
    # Para recargar hay que reiniciar el servidor a mano.
    app.run(
        debug=True,
        use_reloader=False,
        port=int(os.environ.get("PORT", 5000)),
    )