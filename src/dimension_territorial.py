
import math
import unicodedata

import pandas as pd
import plotly.graph_objects as go


# ============================================================
# PALETA (misma del CSS: style_dashboards / style_analysis)
# ============================================================

CYAN = '#00f0ff'
PINK = '#ff2bd1'
GREEN = '#7affb2'
YELLOW = '#ffb703'
TEXT = '#d8e2ec'
TEXT_DIM = '#8a97a6'

PALETA = [CYAN, PINK, YELLOW, GREEN, '#9d7bff', '#4cc9f0', '#ff7a59']
COLOR_OTROS = '#5c6b7a'
COLOR_SIN_DATO = '#2a3646'

ESCALA_NEON = [[0, CYAN], [1, PINK]]


# ============================================================
# CATÁLOGO DE PAÍSES → (nombre legible, continente)
# Las claves están normalizadas (sin tildes, mayúsculas).
# ============================================================

PAISES = {
    # ---------------- AMÉRICA ----------------
    'ECUADOR': ('Ecuador', 'América'),
    'ESTADOS UNIDOS': ('Estados Unidos', 'América'),
    'VENEZUELA': ('Venezuela', 'América'),
    'CHILE': ('Chile', 'América'),
    'PANAMA': ('Panamá', 'América'),
    'PERU': ('Perú', 'América'),
    'MEXICO': ('México', 'América'),
    'ARGENTINA': ('Argentina', 'América'),
    'COSTA RICA': ('Costa Rica', 'América'),
    'BRASIL': ('Brasil', 'América'),
    'BOLIVIA': ('Bolivia', 'América'),
    'REPUBLICA DOMINICANA': ('República Dominicana', 'América'),
    'HONDURAS': ('Honduras', 'América'),
    'GUATEMALA': ('Guatemala', 'América'),
    'EL SALVADOR': ('El Salvador', 'América'),
    'CANADA': ('Canadá', 'América'),
    'NICARAGUA': ('Nicaragua', 'América'),
    'PARAGUAY': ('Paraguay', 'América'),
    'CUBA': ('Cuba', 'América'),
    'ARUBA': ('Aruba', 'América'),
    'CURACAO': ('Curazao', 'América'),
    'CURAAO': ('Curazao', 'América'),            # versión con error de codificación
    'URUGUAY': ('Uruguay', 'América'),
    'TRINIDAD Y TOBAGO': ('Trinidad y Tobago', 'América'),
    'HAITI': ('Haití', 'América'),
    'SURINAM': ('Surinam', 'América'),
    'GUYANA': ('Guyana', 'América'),
    'GUYANA FRANCESA': ('Guayana Francesa', 'América'),
    'BONAIRE': ('Bonaire', 'América'),
    'BAHAMAS': ('Bahamas', 'América'),
    'MARTINICA': ('Martinica', 'América'),
    'JAMAICA': ('Jamaica', 'América'),
    'BELICE': ('Belice', 'América'),
    'PUERTO RICO': ('Puerto Rico', 'América'),

    # ---------------- EUROPA ----------------
    'ESPANA': ('España', 'Europa'),
    'ESPAA': ('España', 'Europa'),               # versión con error de codificación
    'ITALIA': ('Italia', 'Europa'),
    'REINO UNIDO': ('Reino Unido', 'Europa'),
    'FRANCIA': ('Francia', 'Europa'),
    'ALEMANIA': ('Alemania', 'Europa'),
    'SUECIA': ('Suecia', 'Europa'),
    'PORTUGAL': ('Portugal', 'Europa'),
    'BELGICA': ('Bélgica', 'Europa'),
    'PAISES BAJOS': ('Países Bajos', 'Europa'),
    'FEDERACION DE RUSIA': ('Rusia', 'Europa'),
    'RUSIA': ('Rusia', 'Europa'),
    'SUIZA': ('Suiza', 'Europa'),
    'AUSTRIA': ('Austria', 'Europa'),
    'GRECIA': ('Grecia', 'Europa'),
    'MALTA': ('Malta', 'Europa'),
    'RUMANIA': ('Rumania', 'Europa'),
    'REPUBLICA CHECA': ('República Checa', 'Europa'),
    'FINLANDIA': ('Finlandia', 'Europa'),
    'ALBANIA': ('Albania', 'Europa'),
    'POLONIA': ('Polonia', 'Europa'),
    'DINAMARCA': ('Dinamarca', 'Europa'),
    'MONTENEGRO': ('Montenegro', 'Europa'),
    'CROACIA': ('Croacia', 'Europa'),
    'BIELORRUSIA': ('Bielorrusia', 'Europa'),
    'ESLOVENIA': ('Eslovenia', 'Europa'),
    'NORUEGA': ('Noruega', 'Europa'),
    'IRLANDA': ('Irlanda', 'Europa'),
    'HUNGRIA': ('Hungría', 'Europa'),
    'UCRANIA': ('Ucrania', 'Europa'),
    'GEORGIA': ('Georgia', 'Europa'),
    'TURQUIA': ('Turquía', 'Asia'),

    # ---------------- ASIA ----------------
    'JAPON': ('Japón', 'Asia'),
    'HONG KONG': ('Hong Kong', 'Asia'),
    'CHINA': ('China', 'Asia'),
    'ISRAEL': ('Israel', 'Asia'),
    'TAILANDIA': ('Tailandia', 'Asia'),
    'EMIRATOS ARABES UNIDOS': ('Emiratos Árabes Unidos', 'Asia'),
    'VIET NAM': ('Vietnam', 'Asia'),
    'VIETNAM': ('Vietnam', 'Asia'),
    'INDIA': ('India', 'Asia'),
    'QATAR': ('Catar', 'Asia'),
    'SINGAPUR': ('Singapur', 'Asia'),
    'CAMBOYA': ('Camboya', 'Asia'),
    'MALASIA': ('Malasia', 'Asia'),
    'COREA, REPUBLICA DE': ('Corea del Sur', 'Asia'),
    'COREA DEL SUR': ('Corea del Sur', 'Asia'),
    'KAZAJSTAN': ('Kazajistán', 'Asia'),
    'FILIPINAS': ('Filipinas', 'Asia'),
    'LIBANO': ('Líbano', 'Asia'),
    'INDONESIA': ('Indonesia', 'Asia'),

    # ---------------- ÁFRICA ----------------
    'EGIPTO': ('Egipto', 'África'),
    'SUDAFRICA': ('Sudáfrica', 'África'),
    'KENIA': ('Kenia', 'África'),
    'MARRUECOS': ('Marruecos', 'África'),
    'TOGO': ('Togo', 'África'),
    'SENEGAL': ('Senegal', 'África'),
    'MOZAMBIQUE': ('Mozambique', 'África'),
    'GHANA': ('Ghana', 'África'),
    'TANZANIA, REPUBLICA UNIDA DE': ('Tanzania', 'África'),
    'ETIOPIA': ('Etiopía', 'África'),
    'NIGERIA': ('Nigeria', 'África'),
    'GUINEA': ('Guinea', 'África'),

    # ---------------- OCEANÍA ----------------
    'AUSTRALIA': ('Australia', 'Oceanía'),
    'NUEVA ZELANDA': ('Nueva Zelanda', 'Oceanía'),
}

# Valores de PAÍS PRISIÓN que NO son un territorio
SIN_PAIS = {'DESCONOCIDO', 'SIN INFORMACION', 'NO REPORTA', ''}
PROCESO = {'EXTRADICION', 'REPATRIACION', 'EXTRADICION, REPATRIACION'}

LABEL_DESCONOCIDO = 'Desconocido'
LABEL_PROCESO = 'Extradición / repatriación'

ICONOS_CONTINENTE = {
    'América': '🌎',
    'Europa': '🌍',
    'África': '🌍',
    'Asia': '🌏',
    'Oceanía': '🌏',
}

ORDEN_CONTINENTES = ['América', 'Europa', 'Asia', 'África', 'Oceanía']

# Delitos: normalizado → nombre legible
DELITOS = {
    'NARCOTRAFICO': 'Narcotráfico',
    'NARCOTRFICO': 'Narcotráfico',
    'ROBO / HURTO': 'Robo / hurto',
    'HOMICIDIO / TENTATIVA DE': 'Homicidio / tentativa',
    'DELITOS SEXUALES': 'Delitos sexuales',
    'DELITO MIGRATORIO': 'Delito migratorio',
    'PORTE ILEGAL DE ARMAS': 'Porte ilegal de armas',
    'SECUESTRO': 'Secuestro',
    'CRIMEN ORGANIZADO': 'Crimen organizado',
    'FRAUDE / ESTAFA': 'Fraude / estafa',
    'LESIONES PERSONALES': 'Lesiones personales',
    'LAVADO DE ACTIVOS': 'Lavado de activos',
    'EXTORSION': 'Extorsión',
    'EXTORSIN': 'Extorsión',
    'VIOLENCIA INTRAFAMILIAR': 'Violencia intrafamiliar',
    'CONTRABANDO': 'Contrabando',
    'TRATA DE PERSONAS': 'Trata de personas',
    'OTROS': 'Otros',
}

DELITOS_SIN_DATO = {'DESCONOCIDO', 'NO REPORTA - CONFIDENCIALIDAD ESTATAL',
                    'NO REPORTA  CONFIDENCIALIDAD ESTATAL', 'NO REPORTA',
                    'SIN INFORMACION'}
LABEL_DELITO_SIN_DATO = 'Sin dato / confidencial'


# ============================================================
# UTILIDADES DE TEXTO
# ============================================================

def _arreglar_codificacion(texto):
    """Corrige textos UTF-8 leídos como latin-1 (ej. 'ESPAÃ‘A')."""
    if 'Ã' in texto or 'Â' in texto:
        try:
            return texto.encode('latin-1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            return texto
    return texto


def normalizar(valor):
    """Mayúsculas, sin tildes, sin caracteres dañados (�)."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return ''
    texto = _arreglar_codificacion(str(valor).strip())
    texto = texto.replace('�', '').replace('–', '-').replace('—', '-')
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return ' '.join(texto.upper().split())


def _clave_columna(nombre):
    return ''.join(c for c in normalizar(nombre) if c.isalnum())


def _buscar_columna(df, *candidatos):
    mapa = {_clave_columna(c): c for c in df.columns}
    for candidato in candidatos:
        col = mapa.get(_clave_columna(candidato))
        if col is not None:
            return col
    return None


def _formato(n):
    return f"{int(round(n)):,}"


def _pct(parte, total):
    return (parte / total * 100) if total else 0.0


# ============================================================
# PREPARACIÓN DEL DATAFRAME
# ============================================================

def _por_valor_unico(serie, funcion):
    """
    Aplica `funcion` una sola vez por valor distinto y proyecta el
    resultado con map (mismo criterio que normalizar_columna de app.py).
    Evita recorrer las ~388.000 filas una por una.
    """
    serie = serie.fillna('')
    equivalentes = {v: funcion(v) for v in serie.unique()}
    return serie.map(equivalentes)


def _clasificar_pais(valor):
    clave = normalizar(valor)
    if clave in PAISES:
        nombre, cont = PAISES[clave]
        return (nombre, cont, 'País')
    if clave in SIN_PAIS:
        return (LABEL_DESCONOCIDO, 'Sin identificar', 'Sin país')
    if clave in PROCESO:
        return (LABEL_PROCESO, 'Sin identificar', 'Proceso')
    # País no catalogado: se conserva, continente "Otro"
    return (clave.title(), 'Otro', 'País')


def _limpiar_consulado(valor):
    clave = normalizar(valor)
    if not clave:
        return LABEL_DESCONOCIDO
    if clave == 'BTA. ASISTENCIA':
        return 'Bogota (Asistencia Central)'
    if clave.startswith('C.'):
        clave = clave[2:].strip()
    return clave.title()


def _limpiar_delito(valor):
    clave = normalizar(valor)
    if clave in DELITOS_SIN_DATO or clave.startswith('NO REPORTA') or clave == '':
        return LABEL_DELITO_SIN_DATO
    return DELITOS.get(clave, clave.capitalize())


def _a_numero(serie):
    """Convierte a número aceptando coma decimal ('4,61' → 4.61)."""
    texto = serie.astype(str).str.strip().str.replace(',', '.', regex=False)
    return pd.to_numeric(texto, errors='coerce')


_CACHE = {}


def preparar_territorial(df):
    """
    Devuelve un DataFrame con columnas estandarizadas:
    CANTIDAD, PAIS, CONTINENTE, TIPO_TERRITORIO, CONSULADO,
    DELITO, LAT, LON

    El resultado se guarda en caché para el mismo DataFrame, así la
    preparación se paga una sola vez por proceso.
    """
    if _CACHE.get('origen') is df:
        return _CACHE['preparado']

    c_cant = _buscar_columna(df, 'CANTIDAD')
    c_pais = _buscar_columna(df, 'PAIS', 'PAÍS PRISIÓN', 'PAIS PRISION', 'pais_prisi_n')
    c_cons = _buscar_columna(df, 'CONSULADO')
    c_del = _buscar_columna(df, 'DELITO')
    c_lat = _buscar_columna(df, 'LATITUD', 'LAT')
    c_lon = _buscar_columna(df, 'LONGITUD', 'LON', 'LNG')

    if c_cant is None or c_pais is None:
        raise KeyError(
            'El DataFrame necesita al menos las columnas CANTIDAD y PAÍS PRISIÓN.'
        )

    t = pd.DataFrame(index=df.index)
    t['CANTIDAD'] = pd.to_numeric(df[c_cant], errors='coerce').fillna(0)

    # ---------- País + continente ----------
    clasif = _por_valor_unico(df[c_pais], _clasificar_pais)
    t['PAIS'] = clasif.str[0]
    t['CONTINENTE'] = clasif.str[1]
    t['TIPO_TERRITORIO'] = clasif.str[2]

    # ---------- Consulado ----------
    if c_cons is not None:
        t['CONSULADO'] = _por_valor_unico(df[c_cons], _limpiar_consulado)
    else:
        t['CONSULADO'] = LABEL_DESCONOCIDO

    # ---------- Delito ----------
    if c_del is not None:
        t['DELITO'] = _por_valor_unico(df[c_del], _limpiar_delito)
    else:
        t['DELITO'] = LABEL_DELITO_SIN_DATO

    # ---------- Coordenadas ----------
    t['LAT'] = _a_numero(df[c_lat]) if c_lat else float('nan')
    t['LON'] = _a_numero(df[c_lon]) if c_lon else float('nan')

    # Si no hay columnas de latitud/longitud (o vienen vacías), se intenta
    # con la columna geocodificada: "POINT (-78.5 -0.2)" → lon, lat
    if t['LAT'].isna().all() or t['LON'].isna().all():
        c_geo = _buscar_columna(df, 'GEOCODED COLUMN', 'geocoded_column',
                                'GEOCODED', 'UBICACION', 'COORDENADAS')
        if c_geo is not None:
            puntos = df[c_geo].astype(str).str.extract(
                r'(-?\d+(?:[.,]\d+)?)\s+(-?\d+(?:[.,]\d+)?)'
            )
            t['LON'] = _a_numero(puntos[0])
            t['LAT'] = _a_numero(puntos[1])

    _CACHE['origen'] = df
    _CACHE['preparado'] = t
    return t


# ============================================================
# ESTILO COMÚN DE PLOTLY
# ============================================================

def _estilo(fig, alto=420, **extra):
    layout = dict(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Share Tech Mono, monospace', color=TEXT, size=12),
        margin=dict(l=10, r=20, t=20, b=10),
        height=alto,
        hoverlabel=dict(
            bgcolor='#0a1620',
            bordercolor=CYAN,
            font=dict(family='Share Tech Mono, monospace', color='#ffffff'),
        ),
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color=TEXT_DIM)),
    )
    layout.update(extra)          # cada gráfica puede sobrescribir margin, legend…
    fig.update_layout(**layout)
    fig.update_xaxes(gridcolor='rgba(0,240,255,0.08)', zeroline=False,
                     linecolor='rgba(0,240,255,0.2)', tickfont=dict(color=TEXT_DIM))
    fig.update_yaxes(gridcolor='rgba(0,240,255,0.08)', zeroline=False,
                     linecolor='rgba(0,240,255,0.2)', tickfont=dict(color=TEXT))
    return fig


class _Renderizador:
    """Incluye plotly.js (CDN) solo en la primera gráfica de la página."""

    def __init__(self):
        self.primera = True

    def html(self, fig):
        incluir = 'cdn' if self.primera else False
        self.primera = False
        return fig.to_html(
            full_html=False,
            include_plotlyjs=incluir,
            config={'responsive': True, 'displaylogo': False,
                    'displayModeBar': False},
        )


def _sin_datos(mensaje='No hay datos para la combinación de filtros seleccionada.'):
    return (
        '<div class="chart-interpretation" style="border-top:none">'
        f'<p>{mensaje}</p></div>'
    )


# ============================================================
# GRÁFICAS
# ============================================================

ISO3 = {
    'Ecuador': 'ECU', 'Estados Unidos': 'USA', 'Venezuela': 'VEN', 'Chile': 'CHL',
    'Panamá': 'PAN', 'Perú': 'PER', 'México': 'MEX', 'Argentina': 'ARG',
    'Costa Rica': 'CRI', 'Brasil': 'BRA', 'Bolivia': 'BOL',
    'República Dominicana': 'DOM', 'Honduras': 'HND', 'Guatemala': 'GTM',
    'El Salvador': 'SLV', 'Canadá': 'CAN', 'Nicaragua': 'NIC', 'Paraguay': 'PRY',
    'Cuba': 'CUB', 'Aruba': 'ABW', 'Curazao': 'CUW', 'Uruguay': 'URY',
    'Trinidad y Tobago': 'TTO', 'Haití': 'HTI', 'Surinam': 'SUR', 'Guyana': 'GUY',
    'Guayana Francesa': 'GUF', 'Bonaire': 'BES', 'Bahamas': 'BHS',
    'Martinica': 'MTQ', 'Jamaica': 'JAM', 'Belice': 'BLZ', 'Puerto Rico': 'PRI',
    'España': 'ESP', 'Italia': 'ITA', 'Reino Unido': 'GBR', 'Francia': 'FRA',
    'Alemania': 'DEU', 'Suecia': 'SWE', 'Portugal': 'PRT', 'Bélgica': 'BEL',
    'Países Bajos': 'NLD', 'Rusia': 'RUS', 'Suiza': 'CHE', 'Austria': 'AUT',
    'Grecia': 'GRC', 'Malta': 'MLT', 'Rumania': 'ROU', 'República Checa': 'CZE',
    'Finlandia': 'FIN', 'Albania': 'ALB', 'Polonia': 'POL', 'Dinamarca': 'DNK',
    'Montenegro': 'MNE', 'Croacia': 'HRV', 'Bielorrusia': 'BLR',
    'Eslovenia': 'SVN', 'Noruega': 'NOR', 'Irlanda': 'IRL', 'Hungría': 'HUN',
    'Ucrania': 'UKR', 'Georgia': 'GEO', 'Turquía': 'TUR',
    'Japón': 'JPN', 'Hong Kong': 'HKG', 'China': 'CHN', 'Israel': 'ISR',
    'Tailandia': 'THA', 'Emiratos Árabes Unidos': 'ARE', 'Vietnam': 'VNM',
    'India': 'IND', 'Catar': 'QAT', 'Singapur': 'SGP', 'Camboya': 'KHM',
    'Malasia': 'MYS', 'Corea del Sur': 'KOR', 'Kazajistán': 'KAZ',
    'Filipinas': 'PHL', 'Líbano': 'LBN', 'Indonesia': 'IDN',
    'Egipto': 'EGY', 'Sudáfrica': 'ZAF', 'Kenia': 'KEN', 'Marruecos': 'MAR',
    'Togo': 'TGO', 'Senegal': 'SEN', 'Mozambique': 'MOZ', 'Ghana': 'GHA',
    'Tanzania': 'TZA', 'Etiopía': 'ETH', 'Nigeria': 'NGA', 'Guinea': 'GIN',
    'Australia': 'AUS', 'Nueva Zelanda': 'NZL',
}


def _estilo_geo(fig):
    fig.update_geos(
        projection_type='natural earth',
        showland=True, landcolor='#0d1626',
        showocean=True, oceancolor='#050510',
        showcountries=True, countrycolor='rgba(0,240,255,0.18)',
        showcoastlines=True, coastlinecolor='rgba(0,240,255,0.30)',
        showframe=False,
        bgcolor='rgba(0,0,0,0)',
        lataxis_range=[-58, 75],
    )
    _estilo(fig, alto=460, margin=dict(l=0, r=0, t=0, b=0))


def grafica_mapa(t, paises, render):
    """
    Mapa territorial. Devuelve (html, modo):
      · modo 'consulado' → burbujas por consulado si hay LATITUD / LONGITUD.
      · modo 'pais'      → mapa coloreado por país (no depende de coordenadas).
    """
    g = t[t['LAT'].notna() & t['LON'].notna()
          & (t['LAT'] != 0) & (t['LON'] != 0)
          & t['LAT'].between(-90, 90) & t['LON'].between(-180, 180)
          & ~t['CONSULADO'].str.contains('Asistencia', case=False)]

    if not g.empty:
        g = (g.groupby('CONSULADO')
               .agg(CANTIDAD=('CANTIDAD', 'sum'),
                    LAT=('LAT', 'median'),
                    LON=('LON', 'median'),
                    PAIS=('PAIS', lambda s: s.mode().iat[0] if not s.mode().empty else ''))
               .reset_index())
        g = g[g['CANTIDAD'] > 0].sort_values('CANTIDAD')

    # ---------- Modo 1: burbujas por consulado ----------
    if not g.empty:
        total = g['CANTIDAD'].sum()
        g['PCT'] = g['CANTIDAD'] / total * 100
        sizeref = 2.0 * g['CANTIDAD'].max() / (42 ** 2)

        fig = go.Figure(go.Scattergeo(
            lon=g['LON'],
            lat=g['LAT'],
            mode='markers',
            customdata=g[['CONSULADO', 'PAIS', 'CANTIDAD', 'PCT']].values,
            hovertemplate=(
                '<b>%{customdata[0]}</b><br>'
                'País predominante: %{customdata[1]}<br>'
                'Cantidad: %{customdata[2]:,.0f}<br>'
                'Participación: %{customdata[3]:.2f}%<extra></extra>'
            ),
            marker=dict(
                size=g['CANTIDAD'],
                sizemode='area',
                sizeref=sizeref,
                sizemin=3,
                color=g['CANTIDAD'],
                colorscale=ESCALA_NEON,
                opacity=0.75,
                line=dict(width=0.8, color='rgba(255,255,255,0.5)'),
                showscale=False,
            ),
        ))
        _estilo_geo(fig)
        return render.html(fig), 'consulado'

    # ---------- Modo 2: mapa coloreado por país ----------
    p = paises.assign(ISO3=paises['PAIS'].map(ISO3)).dropna(subset=['ISO3'])
    if p.empty:
        return _sin_datos(), 'ninguno'

    fig = go.Figure(go.Choropleth(
        locations=p['ISO3'],
        z=p['CANTIDAD'],
        text=p['PAIS'],
        customdata=p[['PCT']].values,
        colorscale=[[0, '#0b2a3a'], [0.35, CYAN], [1, PINK]],
        marker_line_color='rgba(0,240,255,0.35)',
        marker_line_width=0.5,
        showscale=False,
        hovertemplate=('<b>%{text}</b><br>Cantidad: %{z:,.0f}'
                       '<br>Participación: %{customdata[0]:.2f}%<extra></extra>'),
    ))
    _estilo_geo(fig)
    return render.html(fig), 'pais'


def grafica_paises(paises, render):
    """Top 12 países por participación (sobre población con país identificado)."""
    if paises.empty:
        return _sin_datos()

    top = paises.head(12).iloc[::-1]
    fig = go.Figure(go.Bar(
        x=top['PCT'],
        y=top['PAIS'],
        orientation='h',
        text=[f"{p:.1f}%" for p in top['PCT']],
        textposition='outside',
        cliponaxis=False,
        textfont=dict(color=TEXT),
        customdata=top[['CANTIDAD']].values,
        hovertemplate=('<b>%{y}</b><br>Cantidad: %{customdata[0]:,.0f}'
                       '<br>Participación: %{x:.2f}%<extra></extra>'),
        marker=dict(
            color=top['PCT'],
            colorscale=ESCALA_NEON,
            line=dict(width=1, color='rgba(255,255,255,0.25)'),
        ),
    ))
    _estilo(fig, alto=460)
    fig.update_xaxes(title_text='% de la población con país identificado',
                     title_font=dict(color=TEXT_DIM, size=11), ticksuffix='%')
    return render.html(fig)


def grafica_continentes(continentes, render):
    """Dona por continente."""
    if continentes.empty:
        return _sin_datos()

    colores = [PALETA[i % len(PALETA)] for i in range(len(continentes))]
    fig = go.Figure(go.Pie(
        labels=continentes['CONTINENTE'],
        values=continentes['CANTIDAD'],
        hole=0.58,
        sort=False,
        direction='clockwise',
        textinfo='percent',
        textfont=dict(color='#050510', size=12),
        marker=dict(colors=colores, line=dict(color='#050510', width=2)),
        hovertemplate=('<b>%{label}</b><br>Cantidad: %{value:,.0f}'
                       '<br>Participación: %{percent}<extra></extra>'),
    ))
    _estilo(fig, alto=400,
            legend=dict(orientation='h', y=-0.08, x=0.5, xanchor='center',
                        bgcolor='rgba(0,0,0,0)', font=dict(color=TEXT_DIM)))
    return render.html(fig)


def grafica_consulados(consulados, render):
    """Top 15 consulados (zonas / ciudades)."""
    if consulados.empty:
        return _sin_datos()

    top = consulados.head(15).iloc[::-1]
    fig = go.Figure(go.Bar(
        x=top['CANTIDAD'],
        y=top['CONSULADO'],
        orientation='h',
        text=[f"{p:.1f}%" for p in top['PCT']],
        textposition='outside',
        cliponaxis=False,
        textfont=dict(color=TEXT),
        customdata=top[['PAIS', 'PCT']].values,
        hovertemplate=('<b>%{y}</b><br>País predominante: %{customdata[0]}'
                       '<br>Cantidad: %{x:,.0f}'
                       '<br>Participación: %{customdata[1]:.2f}%<extra></extra>'),
        marker=dict(
            color=top['CANTIDAD'],
            colorscale=[[0, '#0b4f6c'], [0.5, CYAN], [1, PINK]],
            line=dict(width=1, color='rgba(255,255,255,0.25)'),
        ),
    ))
    _estilo(fig, alto=500)
    fig.update_xaxes(title_text='Cantidad', title_font=dict(color=TEXT_DIM, size=11))
    return render.html(fig)


def grafica_perfil_delictivo(perfil, categorias, render):
    """Barras 100 % apiladas: composición del delito en los principales países."""
    if perfil.empty:
        return _sin_datos()

    colores = {}
    i = 0
    for cat in categorias:
        if cat == 'Otros delitos':
            colores[cat] = COLOR_OTROS
        elif cat == LABEL_DELITO_SIN_DATO:
            colores[cat] = COLOR_SIN_DATO
        else:
            colores[cat] = PALETA[i % len(PALETA)]
            i += 1

    paises_orden = list(perfil.index)[::-1]
    fig = go.Figure()
    for cat in categorias:
        valores = perfil.loc[paises_orden, cat] if cat in perfil.columns else [0] * len(paises_orden)
        fig.add_trace(go.Bar(
            name=cat,
            x=valores,
            y=paises_orden,
            orientation='h',
            marker=dict(color=colores[cat], line=dict(width=0.5, color='#050510')),
            hovertemplate=('<b>%{y}</b><br>' + cat +
                           ': %{x:.1f}%<extra></extra>'),
        ))
    _estilo(fig, alto=480, barmode='stack',
            legend=dict(orientation='h', y=-0.12, x=0.5, xanchor='center',
                        bgcolor='rgba(0,0,0,0)', font=dict(color=TEXT_DIM, size=11)))
    fig.update_xaxes(range=[0, 100], ticksuffix='%')
    return render.html(fig)


# ============================================================
# CONTEXTO PARA LA PLANTILLA
# ============================================================

def construir_contexto_territorial(df, continente='', delito=''):
    base = preparar_territorial(df)

    # ---------- listas de filtros (sobre todo el dataset) ----------
    conts_presentes = set(base.loc[base['TIPO_TERRITORIO'] == 'País', 'CONTINENTE'])
    lista_continentes = [c for c in ORDEN_CONTINENTES if c in conts_presentes]
    lista_continentes += sorted(conts_presentes - set(lista_continentes))

    lista_delitos = (base.groupby('DELITO')['CANTIDAD'].sum()
                         .sort_values(ascending=False).index.tolist())

    # ---------- aplicar filtros ----------
    t = base
    if continente:
        t = t[t['CONTINENTE'] == continente]
    if delito:
        t = t[t['DELITO'] == delito]

    poblacion_total = float(t['CANTIDAD'].sum())
    total_registros = int(len(t))

    identificados = t[t['TIPO_TERRITORIO'] == 'País']
    poblacion_identificada = float(identificados['CANTIDAD'].sum())
    poblacion_sin_pais = poblacion_total - poblacion_identificada

    # ---------- agregados por país ----------
    paises = (identificados.groupby('PAIS', as_index=False)['CANTIDAD'].sum()
                           .query('CANTIDAD > 0')
                           .sort_values('CANTIDAD', ascending=False)
                           .reset_index(drop=True))
    paises['PCT'] = paises['CANTIDAD'] / poblacion_identificada * 100 if poblacion_identificada else 0

    # ---------- agregados por continente ----------
    continentes = (identificados.groupby('CONTINENTE', as_index=False)['CANTIDAD'].sum()
                                .query('CANTIDAD > 0')
                                .sort_values('CANTIDAD', ascending=False)
                                .reset_index(drop=True))
    continentes['PCT'] = continentes['CANTIDAD'] / poblacion_identificada * 100 if poblacion_identificada else 0

    # ---------- agregados por consulado ----------
    consulados = (t.groupby('CONSULADO')
                   .agg(CANTIDAD=('CANTIDAD', 'sum'),
                        PAIS=('PAIS', lambda s: s[s != LABEL_DESCONOCIDO].mode().iat[0]
                              if not s[s != LABEL_DESCONOCIDO].mode().empty else LABEL_DESCONOCIDO))
                   .reset_index())
    consulados = consulados[(consulados['CANTIDAD'] > 0)
                            & (consulados['CONSULADO'] != LABEL_DESCONOCIDO)]
    consulados = consulados.sort_values('CANTIDAD', ascending=False).reset_index(drop=True)
    consulados['PCT'] = consulados['CANTIDAD'] / poblacion_total * 100 if poblacion_total else 0

    # ---------- perfil delictivo de los principales países ----------
    top_paises = paises.head(8)['PAIS'].tolist()
    sub = identificados[identificados['PAIS'].isin(top_paises)]
    delitos_top = (sub[sub['DELITO'] != LABEL_DELITO_SIN_DATO]
                   .groupby('DELITO')['CANTIDAD'].sum()
                   .drop(labels=['Otros'], errors='ignore')
                   .sort_values(ascending=False).head(5).index.tolist())
    sub = sub.assign(CAT=sub['DELITO'].where(
        sub['DELITO'].isin(delitos_top + [LABEL_DELITO_SIN_DATO]), 'Otros delitos'))
    perfil = sub.pivot_table(index='PAIS', columns='CAT', values='CANTIDAD',
                             aggfunc='sum', fill_value=0)
    if not perfil.empty:
        perfil = perfil.loc[[p for p in top_paises if p in perfil.index]]
        perfil = perfil.div(perfil.sum(axis=1).replace(0, 1), axis=0) * 100
    categorias = delitos_top + ['Otros delitos', LABEL_DELITO_SIN_DATO]

    # ---------- KPIs ----------
    n_paises = int(len(paises))
    pais_lider = paises.iloc[0]['PAIS'] if n_paises else '—'
    pct_lider = float(paises.iloc[0]['PCT']) if n_paises else 0.0
    concentracion_top5 = float(paises.head(5)['PCT'].sum()) if n_paises else 0.0
    pct_sin_pais = _pct(poblacion_sin_pais, poblacion_total)

    # ---------- gráficas ----------
    render = _Renderizador()
    html_mapa, modo_mapa = grafica_mapa(t, paises, render)
    contexto_graficas = dict(
        grafica_mapa=html_mapa,
        grafica_paises=grafica_paises(paises, render),
        grafica_continentes=grafica_continentes(continentes, render),
        grafica_consulados=grafica_consulados(consulados, render),
        grafica_perfil=grafica_perfil_delictivo(perfil, categorias, render),
    )

    # ---------- interpretaciones dinámicas ----------
    interp = _interpretaciones(paises, continentes, consulados, perfil,
                               pct_sin_pais, poblacion_total, modo_mapa)

    return dict(
        # filtros
        lista_continentes=lista_continentes,
        lista_delitos=lista_delitos,
        continente_seleccionado=continente,
        delito_seleccionado=delito,
        icono_continente=ICONOS_CONTINENTE.get(continente, '🌐'),
        # KPIs
        poblacion_total=int(poblacion_total),
        total_registros=total_registros,
        n_paises=n_paises,
        n_consulados=int(len(consulados)),
        pais_lider=pais_lider,
        pct_lider=pct_lider,
        concentracion_top5=concentracion_top5,
        pct_sin_pais=pct_sin_pais,
        # gráficas + interpretaciones
        **contexto_graficas,
        **interp,
    )


def _interpretaciones(paises, continentes, consulados, perfil, pct_sin_pais, total,
                      modo_mapa='consulado'):
    sin = 'No hay suficientes datos para interpretar esta gráfica con los filtros actuales.'
    out = {}

    # ----- Mapa -----
    if modo_mapa == 'pais' and not paises.empty:
        top3 = paises.head(3)
        nombres = ', '.join(f"<em>{r.PAIS}</em> ({r.PCT:.1f}%)" for r in top3.itertuples())
        out['interp_mapa'] = (
            f"El color de cada país es más intenso cuanto mayor es la cantidad de "
            f"detenidos. Las mayores concentraciones están en {nombres}. El mapa "
            f"muestra a simple vista que la población se agrupa en el continente "
            f"americano y en España, mientras que el resto del mundo tiene una "
            f"presencia marginal."
        )
    elif not consulados.empty:
        top3 = consulados.head(3)
        nombres = ', '.join(f"<em>{r.CONSULADO}</em> ({r.PCT:.1f}%)" for r in top3.itertuples())
        pct_top10 = consulados.head(10)['PCT'].sum()
        out['interp_mapa'] = (
            f"Cada burbuja es una jurisdicción consular; su tamaño es proporcional a la "
            f"cantidad de detenidos. Las mayores concentraciones están en {nombres}. "
            f"Los 10 consulados principales reúnen el <em>{pct_top10:.1f}%</em> de la "
            f"población filtrada, lo que evidencia una distribución territorial muy "
            f"concentrada en pocos puntos del mapa."
        )
    else:
        out['interp_mapa'] = sin

    # ----- Países -----
    if not paises.empty:
        p1 = paises.iloc[0]
        menor = paises.iloc[-1]
        top5 = paises.head(5)['PCT'].sum()
        out['interp_paises'] = (
            f"Sobre la población con país identificado, <em>{p1.PAIS}</em> lidera con "
            f"el {p1.PCT:.1f}%. Los cinco primeros países concentran el "
            f"<em>{top5:.1f}%</em>, mientras que el territorio con menor registro es "
            f"<em>{menor.PAIS}</em> ({_formato(menor.CANTIDAD)}). Además, el "
            f"<em>{pct_sin_pais:.1f}%</em> de la población no tiene país de prisión "
            f"identificado y queda por fuera de este porcentaje."
        )
    else:
        out['interp_paises'] = sin

    # ----- Continentes -----
    if not continentes.empty:
        c1 = continentes.iloc[0]
        resto = ', '.join(f"{r.CONTINENTE} {r.PCT:.1f}%" for r in continentes.iloc[1:].itertuples())
        out['interp_continentes'] = (
            f"<em>{c1.CONTINENTE}</em> concentra el {c1.PCT:.1f}% de los detenidos con "
            f"país conocido"
            + (f"; le siguen {resto}." if resto else ".")
            + " La detención de colombianos es un fenómeno principalmente regional, "
              "asociado a la cercanía geográfica y a las rutas migratorias."
        )
    else:
        out['interp_continentes'] = sin

    # ----- Consulados -----
    if not consulados.empty:
        c1 = consulados.iloc[0]
        frontera = consulados[consulados['CONSULADO'].str.contains(
            'Tulcan|Esmeraldas|Nueva Loja|San Cristobal|San Ant|Cucuta|Maracaibo',
            case=False, regex=True)]
        txt_frontera = ''
        if not frontera.empty:
            txt_frontera = (
                f" Los consulados de zona de frontera (Ecuador y Venezuela) suman el "
                f"<em>{frontera['PCT'].sum():.1f}%</em>, un comportamiento particular de "
                f"territorios limítrofes con Colombia."
            )
        out['interp_consulados'] = (
            f"A nivel de ciudad, <em>{c1.CONSULADO}</em> es la jurisdicción con más "
            f"detenidos ({c1.PCT:.1f}%). El consulado conserva el dato territorial "
            f"incluso cuando el país de prisión aparece como desconocido, por lo que "
            f"es el nivel más completo del dataset." + txt_frontera
        )
    else:
        out['interp_consulados'] = sin

    # ----- Perfil delictivo -----
    if not perfil.empty:
        notas = []
        sin_dato_col = LABEL_DELITO_SIN_DATO
        delitos_cols = [c for c in perfil.columns if c not in ('Otros delitos', sin_dato_col)]
        if delitos_cols:
            principal = perfil[delitos_cols].idxmax(axis=1)
            for pais, deli in principal.items():
                valor = perfil.loc[pais, deli]
                if valor >= 50:
                    notas.append(f"{pais} ({deli.lower()} {valor:.0f}%)")
        opacos = []
        if sin_dato_col in perfil.columns:
            opacos = [f"{p} ({v:.0f}%)" for p, v in perfil[sin_dato_col].items() if v >= 25]

        partes = ["Cada barra muestra la composición del delito dentro de un mismo país."]
        if notas:
            partes.append("Países con un delito claramente dominante: "
                          f"<em>{', '.join(notas)}</em>.")
        if opacos:
            partes.append("Territorios con alta proporción de delito sin dato o "
                          f"confidencial: <em>{', '.join(opacos)}</em>.")
        partes.append("Las diferencias muestran que cada territorio tiene un perfil "
                      "penal propio y no una réplica del total nacional.")
        out['interp_perfil'] = ' '.join(partes)
    else:
        out['interp_perfil'] = sin

    return out