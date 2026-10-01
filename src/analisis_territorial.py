

import os
import sys

import pandas as pd
import plotly.graph_objects as go

try:                                    # importado desde app.py
    from src import dimension_territorial as territorial
except ImportError:                     # ejecutado como script: python src/analisis_territorial.py
    import dimension_territorial as territorial


# ============================================================
# PARÁMETROS DEL ANÁLISIS
# ============================================================

CYAN = territorial.CYAN
PINK = territorial.PINK
YELLOW = territorial.YELLOW
GREEN = territorial.GREEN
TEXT = territorial.TEXT
TEXT_DIM = territorial.TEXT_DIM
GRIS = '#3d4b5c'

LABEL_DESCONOCIDO = territorial.LABEL_DESCONOCIDO
LABEL_PROCESO = territorial.LABEL_PROCESO
LABEL_DELITO_SIN_DATO = territorial.LABEL_DELITO_SIN_DATO

# Pureza mínima para afirmar que un consulado atiende un solo país. Se
# mide con los registros que SÍ traen país: si al menos el 95 % de las
# personas de un consulado están en un mismo país, ese país se usa para
# los registros del mismo consulado que llegaron sin país.
PUREZA_CONSULADO = 0.95

# Jurisdicciones que no son un territorio en el exterior.
CONSULADOS_NO_TERRITORIALES = {LABEL_DESCONOCIDO, 'Bogota (Asistencia Central)'}

# Consulados en zona de frontera con Colombia (mismo criterio del tablero).
CONSULADOS_FRONTERA = {
    'Tulcan': 'Ecuador',
    'Esmeraldas': 'Ecuador',
    'Nueva Loja': 'Ecuador',
    'San Cristobal': 'Venezuela',
    'San Ant De Tachira': 'Venezuela',
    'Maracaibo': 'Venezuela',
}

# Capitales con las que se compara la carga de los consulados de frontera.
CONSULADOS_CAPITAL = {'Lima': 'Perú', 'Mexico': 'México', 'Caracas': 'Venezuela',
                      'Quito': 'Ecuador'}

# Nombre legible de los consulados para textos y gráficas (la limpieza del
# tablero los deja sin tildes porque los usa como clave).
NOMBRES_CONSULADO = {
    'San Cristobal': 'San Cristóbal', 'Tulcan': 'Tulcán', 'Mexico': 'Ciudad de México',
    'San Ant De Tachira': 'San Antonio del Táchira', 'Panama': 'Panamá',
    'Bogota (Asistencia Central)': 'Bogotá (Asistencia Central)', 'Valencia Ven': 'Valencia (Ven.)',
    'Valencia Esp': 'Valencia (Esp.)', 'San Jose': 'San José', 'Sao Paulo': 'São Paulo',
    'Merida Ven': 'Mérida (Ven.)', 'Puerto Espana': 'Puerto España', 'Moscu': 'Moscú',
    'Asuncion': 'Asunción', 'Bogota': 'Bogotá', 'Brasilia': 'Brasilia',
    'Sto Dom Colorados': 'Santo Domingo de los Colorados', 'Tokio': 'Tokio',
}


def nombre_consulado(c):
    return NOMBRES_CONSULADO.get(c, c)


# Delitos considerados violentos para comparar perfiles.
DELITOS_VIOLENTOS = ['Homicidio / tentativa', 'Secuestro', 'Porte ilegal de armas',
                     'Lesiones personales', 'Extorsión']

# Umbral para decir que un país está "especializado" en narcotráfico.
UMBRAL_NARCO = 70.0

ORDEN_CONTINENTES = territorial.ORDEN_CONTINENTES


# ============================================================
# UTILIDADES
# ============================================================

def _f(n):
    """Entero con separador de miles (mismo formato que el tablero)."""
    return f"{int(round(n)):,}"


def _p(x, dec=1):
    return f"{x:.{dec}f}%"


def _lista(elementos):
    """'a', 'a y b', 'a, b y c'."""
    elementos = list(elementos)
    if not elementos:
        return ''
    if len(elementos) == 1:
        return elementos[0]
    return ', '.join(elementos[:-1]) + ' y ' + elementos[-1]


def _mayuscula(texto):
    """Primera letra en mayúscula sin alterar el resto (str.capitalize sí lo hace)."""
    return texto[:1].upper() + texto[1:]


def _participacion(df, columna):
    """Suma CANTIDAD por `columna` y agrega % sobre el total del subconjunto."""
    out = (df.groupby(columna, as_index=False)['CANTIDAD'].sum()
             .query('CANTIDAD > 0')
             .sort_values('CANTIDAD', ascending=False)
             .reset_index(drop=True))
    total = out['CANTIDAD'].sum()
    out['PCT'] = out['CANTIDAD'] / total * 100 if total else 0.0
    return out


# ============================================================
# 1. PREPARACIÓN
# ============================================================

def preparar_analisis(df):
    """
    Parte de `preparar_territorial` y añade:
      · FECHA / ANIO          → fecha de publicación del corte
      · PAIS_CONSULAR         → país inferido a partir del consulado
      · CONTINENTE_CONSULAR   → continente de ese país
      · PAIS_FINAL / CONTINENTE_FINAL → país reportado si existe; si no,
                                el inferido por el consulado.
    Devuelve (t, tabla_consulados).
    """
    t = territorial.preparar_territorial(df).copy()

    c_fecha = territorial._buscar_columna(df, 'FECHA PUBLICACION', 'FECHA PUBLICACIÓN',
                                          'FECHA', 'fecha_publicaci_n')
    t['FECHA'] = pd.to_datetime(df[c_fecha], errors='coerce') if c_fecha else pd.NaT
    t['ANIO'] = t['FECHA'].dt.year

    tabla = tabla_consulado_pais(t)
    confiables = tabla[tabla['PUREZA'] >= PUREZA_CONSULADO]

    t['PAIS_CONSULAR'] = t['CONSULADO'].map(confiables['PAIS'])
    t['CONTINENTE_CONSULAR'] = t['CONSULADO'].map(confiables['CONTINENTE'])

    con_pais = t['TIPO_TERRITORIO'] == 'País'
    t['PAIS_FINAL'] = t['PAIS'].where(con_pais, t['PAIS_CONSULAR'])
    t['CONTINENTE_FINAL'] = t['CONTINENTE'].where(con_pais, t['CONTINENTE_CONSULAR'])
    return t, tabla


def tabla_consulado_pais(t):
    """
    Para cada consulado, el país donde está la mayor parte de su población
    (según los registros con país reportado) y la PUREZA de esa relación.
    """
    ident = t[(t['TIPO_TERRITORIO'] == 'País')
              & ~t['CONSULADO'].isin(CONSULADOS_NO_TERRITORIALES)]
    cp = (ident.groupby(['CONSULADO', 'PAIS', 'CONTINENTE'], as_index=False)['CANTIDAD']
               .sum())
    cp['TOTAL_CONSULADO'] = cp.groupby('CONSULADO')['CANTIDAD'].transform('sum')
    cp['PUREZA'] = cp['CANTIDAD'] / cp['TOTAL_CONSULADO']
    return (cp.sort_values('PUREZA', ascending=False)
              .drop_duplicates('CONSULADO')
              .set_index('CONSULADO')
              .sort_values('TOTAL_CONSULADO', ascending=False))


# ============================================================
# 2. CONOCIMIENTOS EVIDENTES (CÁLCULO)
# ============================================================

def calcular_calidad_territorial(t, tabla):
    """C5 — El país de prisión deja de reportarse y el consulado lo sustituye."""
    anual = (t.groupby(['ANIO', 'TIPO_TERRITORIO'])['CANTIDAD'].sum()
               .unstack(fill_value=0))
    for col in ('País', 'Sin país', 'Proceso'):
        if col not in anual.columns:
            anual[col] = 0
    pct = anual.div(anual.sum(axis=1), axis=0) * 100
    pct = pct[['País', 'Proceso', 'Sin país']].reset_index()

    # Primer año en que prácticamente ningún registro trae país (< 1 %).
    sin_reporte = pct[pct['País'] < 1]['ANIO']
    anio_quiebre = int(sin_reporte.min()) if not sin_reporte.empty else None

    total = t['CANTIDAD'].sum()
    sin_pais = t[t['TIPO_TERRITORIO'] != 'País']
    con_consulado = t[~t['CONSULADO'].isin({LABEL_DESCONOCIDO})]
    recuperado = sin_pais['PAIS_CONSULAR'].notna()

    return dict(
        anual=pct,
        anio_inicio=int(t['ANIO'].min()),
        anio_fin=int(t['ANIO'].max()),
        anio_quiebre=anio_quiebre,
        pct_sin_pais_total=float(sin_pais['CANTIDAD'].sum() / total * 100),
        pct_sin_pais_inicio=float(pct.iloc[0]['Sin país'] + pct.iloc[0]['Proceso']),
        pct_sin_pais_previo=(float(pct[pct['ANIO'] == anio_quiebre - 1]
                                   [['Sin país', 'Proceso']].sum(axis=1).iloc[0])
                             if anio_quiebre and (pct['ANIO'] == anio_quiebre - 1).any()
                             else None),
        pct_consulado_diligenciado=float(con_consulado['CANTIDAD'].sum() / total * 100),
        n_consulados=int(t.loc[~t['CONSULADO'].isin(CONSULADOS_NO_TERRITORIALES),
                               'CONSULADO'].nunique()),
        n_consulados_con_pais=int(len(tabla)),
        n_consulados_puros=int((tabla['PUREZA'] >= PUREZA_CONSULADO).sum()),
        pct_recuperado=float(sin_pais.loc[recuperado, 'CANTIDAD'].sum()
                             / sin_pais['CANTIDAD'].sum() * 100) if len(sin_pais) else 0.0,
        pct_cobertura_final=float(t.loc[t['PAIS_FINAL'].notna(), 'CANTIDAD'].sum()
                                  / total * 100),
    )


def calcular_concentracion(t):
    """C1 — Pocos países concentran la mayoría de los detenidos."""
    ident = t[t['TIPO_TERRITORIO'] == 'País']
    paises = _participacion(ident, 'PAIS')
    paises['ACUM'] = paises['PCT'].cumsum()

    # Índice de Herfindahl-Hirschman (0-10.000): > 1.500 = concentración moderada
    hhi = float((paises['PCT'] ** 2).sum())
    n_80 = int((paises['ACUM'] < 80).sum() + 1)

    # Robustez: país final (reportado + inferido por consulado) y último corte
    final = _participacion(t.dropna(subset=['PAIS_FINAL']), 'PAIS_FINAL')
    ultimo = t[t['FECHA'] == t['FECHA'].max()]
    ultimo_final = _participacion(ultimo.dropna(subset=['PAIS_FINAL']), 'PAIS_FINAL')

    return dict(
        paises=paises,
        n_paises=int(len(paises)),
        top5=paises.head(5),
        pct_top5=float(paises.head(5)['PCT'].sum()),
        pct_top10=float(paises.head(10)['PCT'].sum()),
        n_80=n_80,
        hhi=hhi,
        n_efectivo=10000 / hhi if hhi else 0.0,
        poblacion_identificada=float(ident['CANTIDAD'].sum()),
        final=final,
        pct_top5_final=float(final.head(5)['PCT'].sum()),
        ultimo_fecha=t['FECHA'].max(),
        ultimo_total=float(ultimo['CANTIDAD'].sum()),
        ultimo_final=ultimo_final,
        pct_top5_ultimo=float(ultimo_final.head(5)['PCT'].sum()),
    )


def calcular_continentes(t, anio_quiebre):
    """C2 — El fenómeno es regional: América, y Europa a través de España."""
    ident = t[t['TIPO_TERRITORIO'] == 'País']
    cont = _participacion(ident, 'CONTINENTE')
    orden = {c: i for i, c in enumerate(ORDEN_CONTINENTES)}
    cont = cont.assign(_o=cont['CONTINENTE'].map(orden).fillna(99)).sort_values('_o')

    # Peso de España dentro de Europa
    europa = ident[ident['CONTINENTE'] == 'Europa']
    pct_espana_europa = (float(europa.loc[europa['PAIS'] == 'España', 'CANTIDAD'].sum()
                               / europa['CANTIDAD'].sum() * 100)
                         if europa['CANTIDAD'].sum() else 0.0)

    # Comparación por periodos: país reportado vs. país inferido por consulado
    periodos = []
    if anio_quiebre:
        antes = t[(t['ANIO'] < anio_quiebre) & (t['TIPO_TERRITORIO'] == 'País')]
        despues = t[(t['ANIO'] >= anio_quiebre)].dropna(subset=['CONTINENTE_FINAL'])
        etiquetas = (f"{int(t['ANIO'].min())}–{anio_quiebre - 1} · país reportado",
                     f"{anio_quiebre}–{int(t['ANIO'].max())} · país inferido por consulado")
        for etiqueta, sub in zip(etiquetas, (antes, despues)):
            p = _participacion(sub, 'CONTINENTE_FINAL' if 'inferido' in etiqueta else 'CONTINENTE')
            p.columns = ['CONTINENTE', 'CANTIDAD', 'PCT']
            p['PERIODO'] = etiqueta
            periodos.append(p)
    periodos = pd.concat(periodos, ignore_index=True) if periodos else pd.DataFrame()

    def pct_de(df, nombre):
        fila = df[df['CONTINENTE'] == nombre]
        return float(fila['PCT'].iloc[0]) if not fila.empty else 0.0

    pct_america = pct_de(cont, 'América')
    pct_europa = pct_de(cont, 'Europa')
    return dict(
        continentes=cont.drop(columns='_o'),
        pct_america=pct_america,
        pct_europa=pct_europa,
        pct_resto=100 - pct_america - pct_europa,
        pct_espana_europa=pct_espana_europa,
        periodos=periodos,
        pct_america_despues=(pct_de(periodos[periodos['PERIODO'].str.contains('inferido')],
                                    'América') if not periodos.empty else None),
        pct_europa_despues=(pct_de(periodos[periodos['PERIODO'].str.contains('inferido')],
                                   'Europa') if not periodos.empty else None),
    )


def calcular_perfil_delictivo(t, n_paises=10):
    """C3 — Cada territorio tiene un delito dominante distinto."""
    ident = t[t['TIPO_TERRITORIO'] == 'País']
    top = _participacion(ident, 'PAIS').head(n_paises)['PAIS'].tolist()

    pv = (ident[ident['PAIS'].isin(top)]
          .pivot_table(index='PAIS', columns='DELITO', values='CANTIDAD',
                       aggfunc='sum', fill_value=0))
    pct = pv.div(pv.sum(axis=1), axis=0) * 100
    pct = pct.loc[top]

    delitos = [d for d in pct.columns if d not in (LABEL_DELITO_SIN_DATO, 'Otros')]
    principales = (ident.groupby('DELITO')['CANTIDAD'].sum()
                        .drop(labels=[LABEL_DELITO_SIN_DATO, 'Otros'], errors='ignore')
                        .sort_values(ascending=False).head(5).index.tolist())

    matriz = pct.reindex(columns=principales, fill_value=0).copy()
    matriz['Otros delitos'] = (pct.drop(columns=principales + [LABEL_DELITO_SIN_DATO],
                                        errors='ignore').sum(axis=1))
    matriz[LABEL_DELITO_SIN_DATO] = pct.get(LABEL_DELITO_SIN_DATO, 0)

    dominante = pct[delitos].idxmax(axis=1)
    narco = pct.get('Narcotráfico', pd.Series(0, index=pct.index))
    violentos = pct.reindex(columns=DELITOS_VIOLENTOS, fill_value=0).sum(axis=1)
    sin_dato = pct.get(LABEL_DELITO_SIN_DATO, pd.Series(0, index=pct.index))

    # País (con volumen relevante, fuera del top) con mayor opacidad del delito
    vol = _participacion(ident, 'PAIS')
    vol = vol[vol['CANTIDAD'] >= 1000]['PAIS']
    sd_todos = (ident[ident['PAIS'].isin(vol)]
                .assign(SD=lambda d: d['DELITO'].eq(LABEL_DELITO_SIN_DATO) * d['CANTIDAD'])
                .groupby('PAIS')[['SD', 'CANTIDAD']].sum())
    sd_todos['PCT'] = sd_todos['SD'] / sd_todos['CANTIDAD'] * 100
    opaco = sd_todos['PCT'].idxmax() if not sd_todos.empty else None

    return dict(
        matriz=matriz,
        dominante=dominante,
        narco=narco,
        violentos=violentos,
        sin_dato=sin_dato,
        sobre_umbral=narco[narco > UMBRAL_NARCO].sort_values(ascending=False),
        cerca_umbral=narco[(narco <= UMBRAL_NARCO) & (narco >= UMBRAL_NARCO - 5)],
        robo=dominante[dominante == 'Robo / hurto'].index.tolist(),
        pais_mas_violento=violentos.idxmax(),
        pct_narco_global=float(ident.loc[ident['DELITO'] == 'Narcotráfico', 'CANTIDAD'].sum()
                               / ident['CANTIDAD'].sum() * 100),
        pais_opaco=opaco,
        pct_opaco=float(sd_todos.loc[opaco, 'PCT']) if opaco else 0.0,
        rango_narco=(float(narco.min()), narco.idxmin(), float(narco.max()), narco.idxmax()),
    )


def calcular_frontera(t):
    """C4 — Los consulados de frontera tienen carga de capital."""
    total = t['CANTIDAD'].sum()
    cons = (t[~t['CONSULADO'].isin(CONSULADOS_NO_TERRITORIALES)]
            .groupby('CONSULADO', as_index=False)['CANTIDAD'].sum()
            .sort_values('CANTIDAD', ascending=False).reset_index(drop=True))
    cons['PCT'] = cons['CANTIDAD'] / total * 100
    cons['PUESTO'] = range(1, len(cons) + 1)
    cons['FRONTERA'] = cons['CONSULADO'].isin(CONSULADOS_FRONTERA)

    frontera = cons[cons['FRONTERA']]
    capitales = cons[cons['CONSULADO'].isin(CONSULADOS_CAPITAL)]

    # Peso de la frontera dentro de cada país vecino (con país final)
    por_pais = {}
    for pais in sorted(set(CONSULADOS_FRONTERA.values())):
        sub = t[t['PAIS_FINAL'] == pais]
        tot_pais = sub['CANTIDAD'].sum()
        if not tot_pais:
            continue
        c = sub.groupby('CONSULADO')['CANTIDAD'].sum().sort_values(ascending=False)
        front = c[c.index.isin(CONSULADOS_FRONTERA)].sum()
        capital = next((k for k, v in CONSULADOS_CAPITAL.items() if v == pais), None)
        por_pais[pais] = dict(
            pct_frontera=float(front / tot_pais * 100),
            capital=capital,
            pct_capital=float(c.get(capital, 0) / tot_pais * 100) if capital else 0.0,
            primero=c.index[0],
            pct_primero=float(c.iloc[0] / tot_pais * 100),
        )

    # Estabilidad: peso de la frontera por año
    anual = (t.assign(F=t['CONSULADO'].isin(CONSULADOS_FRONTERA) * t['CANTIDAD'])
              .groupby('ANIO')[['F', 'CANTIDAD']].sum())
    anual['PCT'] = anual['F'] / anual['CANTIDAD'] * 100

    # Capitales que quedan por debajo de algún consulado de frontera
    mejor_frontera = int(frontera['PUESTO'].min()) if not frontera.empty else None
    superadas = capitales[capitales['PUESTO'] > (frontera['PUESTO'].nsmallest(2).max()
                                                 if len(frontera) >= 2 else 10**6)]

    return dict(
        consulados=cons,
        frontera=frontera,
        capitales=capitales,
        pct_frontera=float(frontera['PCT'].sum()),
        por_pais=por_pais,
        anual=anual['PCT'],
        mejor_puesto=mejor_frontera,
        capitales_superadas=superadas,
        pct_top10=float(cons.head(10)['PCT'].sum()),
    )


# ============================================================
# 3. GRÁFICAS DE EVIDENCIA
# ============================================================

def grafica_k1(c1, render):
    """Pareto de países: barras de participación + curva acumulada (un solo eje en %)."""
    top = c1['paises'].head(12)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Participación del país',
        x=top['PAIS'], y=top['PCT'],
        marker=dict(color=[PINK if i < 5 else CYAN for i in range(len(top))],
                    line=dict(width=0)),
        text=[f"{v:.1f}%" for v in top['PCT']], textposition='outside',
        textfont=dict(color=TEXT), cliponaxis=False,
        customdata=top[['CANTIDAD']].values,
        hovertemplate='<b>%{x}</b><br>Participación: %{y:.2f}%'
                      '<br>Cantidad: %{customdata[0]:,.0f}<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        name='Participación acumulada',
        x=top['PAIS'], y=top['ACUM'], mode='lines+markers',
        line=dict(color=YELLOW, width=2), marker=dict(size=8, color=YELLOW),
        hovertemplate='<b>%{x}</b><br>Acumulado: %{y:.1f}%<extra></extra>',
    ))
    territorial._estilo(fig, alto=420,
                        legend=dict(orientation='h', y=1.08, x=0, bgcolor='rgba(0,0,0,0)',
                                    font=dict(color=TEXT_DIM)))
    fig.update_yaxes(range=[0, 105], ticksuffix='%',
                     title_text='% de la población con país identificado',
                     title_font=dict(color=TEXT_DIM, size=11))
    fig.update_xaxes(tickangle=-35)
    return render.html(fig)


def grafica_k2(c2, render):
    """Continentes por periodo: país reportado vs. país inferido por consulado."""
    per = c2['periodos']
    if per.empty:
        return territorial._sin_datos()
    fig = go.Figure()
    for etiqueta, color in zip(per['PERIODO'].unique(), (CYAN, PINK)):
        sub = (per[per['PERIODO'] == etiqueta]
               .set_index('CONTINENTE').reindex(ORDEN_CONTINENTES).fillna(0)
               .reset_index())
        fig.add_trace(go.Bar(
            name=etiqueta, y=sub['CONTINENTE'], x=sub['PCT'], orientation='h',
            marker=dict(color=color, line=dict(width=0)),
            text=[f"{v:.1f}%" for v in sub['PCT']], textposition='outside',
            textfont=dict(color=TEXT), cliponaxis=False,
            hovertemplate='<b>%{y}</b><br>' + etiqueta + ': %{x:.2f}%<extra></extra>',
        ))
    territorial._estilo(fig, alto=380, barmode='group', bargap=0.25,
                        legend=dict(orientation='h', y=-0.18, x=0.5, xanchor='center',
                                    bgcolor='rgba(0,0,0,0)', font=dict(color=TEXT_DIM)))
    fig.update_yaxes(autorange='reversed')
    fig.update_xaxes(range=[0, 95], ticksuffix='%')
    return render.html(fig)


def grafica_k3(c3, render):
    """Mapa de calor país × delito (% de los casos de cada país)."""
    m = c3['matriz']
    if m.empty:
        return territorial._sin_datos()
    fig = go.Figure(go.Heatmap(
        z=m.values, x=list(m.columns), y=list(m.index),
        colorscale=[[0, '#07121c'], [0.35, '#0b4f6c'], [1, CYAN]],
        zmin=0, zmax=100,
        text=[[f"{v:.0f}%" for v in fila] for fila in m.values],
        texttemplate='%{text}', textfont=dict(size=11),
        xgap=2, ygap=2,
        colorbar=dict(ticksuffix='%', tickfont=dict(color=TEXT_DIM), outlinewidth=0,
                      thickness=10),
        hovertemplate='<b>%{y}</b><br>%{x}: %{z:.1f}% de sus casos<extra></extra>',
    ))
    territorial._estilo(fig, alto=460, margin=dict(l=10, r=10, t=10, b=10))
    fig.update_yaxes(autorange='reversed', gridcolor='rgba(0,0,0,0)')
    fig.update_xaxes(side='top', gridcolor='rgba(0,0,0,0)', tickangle=0)
    return render.html(fig)


def grafica_k4(c4, render):
    """Top 20 consulados, con los de frontera resaltados."""
    top = c4['consulados'].head(20).iloc[::-1]
    colores = [PINK if f else 'rgba(0,240,255,0.55)' for f in top['FRONTERA']]
    fig = go.Figure(go.Bar(
        x=top['PCT'], y=[f"#{p} {nombre_consulado(c)}" for p, c in zip(top['PUESTO'], top['CONSULADO'])],
        orientation='h',
        marker=dict(color=colores, line=dict(width=0)),
        text=[f"{v:.2f}%" for v in top['PCT']], textposition='outside',
        textfont=dict(color=TEXT), cliponaxis=False,
        customdata=top[['CANTIDAD']].values,
        hovertemplate='<b>%{y}</b><br>Participación: %{x:.2f}%'
                      '<br>Cantidad: %{customdata[0]:,.0f}<extra></extra>',
        showlegend=False,
    ))
    # leyenda manual (identidad no solo por color: el texto la nombra)
    for nombre, color in (('Consulado de frontera', PINK),
                          ('Otros consulados', 'rgba(0,240,255,0.55)')):
        fig.add_trace(go.Bar(x=[None], y=[None], name=nombre, marker=dict(color=color)))
    territorial._estilo(fig, alto=560,
                        legend=dict(orientation='h', y=-0.08, x=0.5, xanchor='center',
                                    bgcolor='rgba(0,0,0,0)', font=dict(color=TEXT_DIM)))
    fig.update_xaxes(ticksuffix='%', title_text='% de la población total',
                     title_font=dict(color=TEXT_DIM, size=11))
    return render.html(fig)


def grafica_k5(c5, render):
    """Composición anual del dato territorial (barras 100 % apiladas)."""
    a = c5['anual']
    fig = go.Figure()
    for col, nombre, color in (('País', 'País de prisión reportado', CYAN),
                               ('Proceso', LABEL_PROCESO, YELLOW),
                               ('Sin país', 'País desconocido', GRIS)):
        fig.add_trace(go.Bar(
            name=nombre, x=a['ANIO'].astype(str), y=a[col],
            marker=dict(color=color, line=dict(color='#050510', width=1)),
            hovertemplate='<b>%{x}</b><br>' + nombre + ': %{y:.1f}%<extra></extra>',
        ))
    territorial._estilo(fig, alto=380, barmode='stack',
                        legend=dict(orientation='h', y=-0.15, x=0.5, xanchor='center',
                                    bgcolor='rgba(0,0,0,0)', font=dict(color=TEXT_DIM)))
    fig.update_yaxes(range=[0, 100], ticksuffix='%',
                     title_text='% de la población de cada año',
                     title_font=dict(color=TEXT_DIM, size=11))
    return render.html(fig)


# ============================================================
# 4. REDACCIÓN DE LOS CONOCIMIENTOS
# ============================================================
# Cada conocimiento es un diccionario con la estructura exigida en el
# informe. Los textos admiten <em>/<strong> porque se pintan con |safe.

def _conocimiento_1(c1):
    top5 = c1['top5']
    lista = _lista([f"{r.PAIS} ({r.PCT:.1f}%)" for r in top5.itertuples()])
    ult = c1['ultimo_final'].head(3)
    fecha = c1['ultimo_fecha'].strftime('%d/%m/%Y') if pd.notna(c1['ultimo_fecha']) else '—'
    return dict(
        numero=1,
        titulo='Alta concentración en cinco países',
        pregunta='¿La población detenida está repartida entre muchos países o se '
                 'concentra en unos pocos territorios?',
        variables='PAÍS PRISIÓN (categórica), CANTIDAD (numérica agregadora) y, para '
                  'la comprobación, CONSULADO y FECHA PUBLICACIÓN.',
        procedimiento='Normalización del país (tildes, codificación y alias) con el '
                      'catálogo de dimension_territorial.py; suma de CANTIDAD por país '
                      'sobre la población con país identificado; orden descendente; '
                      'participación acumulada (Pareto) e índice de Herfindahl-Hirschman '
                      '(HHI) y su inverso, el número efectivo de países. Se repite el cálculo con el país inferido por el consulado '
                      'y sobre el último corte publicado.',
        evidencia='Gráfica K1 (Pareto de países) de esta página; gráfica '
                  '"Participación porcentual por país de prisión" y KPI "Concentración '
                  'Top 5" del tablero.',
        hallazgo=(f"Hay detenidos en <strong>{c1['n_paises']}</strong> países, pero cinco "
                  f"reúnen el <strong>{_p(c1['pct_top5'])}</strong>: {lista}. Con solo "
                  f"<strong>{c1['n_80']}</strong> países se supera el 80 % y los diez "
                  f"primeros suman el {_p(c1['pct_top10'])}. El índice de Herfindahl-Hirschman "
                  f"({c1['hhi']:,.0f}) equivale a tener solo <strong>{c1['n_efectivo']:.0f} "
                  f"países efectivos</strong> del mismo tamaño. Al completar el país con el consulado, "
                  f"el top 5 sigue en el {_p(c1['pct_top5_final'])}, y en el último corte "
                  f"({fecha}, {_f(c1['ultimo_total'])} personas) en el "
                  f"{_p(c1['pct_top5_ultimo'])}, encabezado por "
                  f"{_lista([f'{r.PAIS_FINAL} ({r.PCT:.1f}%)' for r in ult.itertuples()])}."),
        interpretacion='La detención de colombianos en el exterior no es un fenómeno '
                       'disperso: una cola larga de países aporta muy poco y el grueso '
                       'se resuelve en un puñado de destinos. Que la concentración se '
                       'mantenga con el país inferido y en el corte más reciente indica '
                       'que no es un efecto de los datos faltantes ni de un año puntual.',
        utilidad='Permite focalizar la capacidad consular (abogados, visitas '
                 'carcelarias, convenios de traslado) en cinco países y cubrir cerca de '
                 'tres de cada cuatro detenidos.',
        limitacion='Los porcentajes se calculan sobre la población con país '
                   'identificado (registros hasta 2022). El total suma 64 cortes de '
                   'publicación, por lo que expresa participación promedio y no número '
                   'de personas distintas.',
    )


def _conocimiento_2(c2):
    despues = ''
    if c2['pct_america_despues'] is not None:
        despues = (f" En el periodo sin país reportado, inferido con el consulado, la "
                   f"proporción casi no cambia: América {_p(c2['pct_america_despues'])} y "
                   f"Europa {_p(c2['pct_europa_despues'])}.")
    return dict(
        numero=2,
        titulo='Un fenómeno regional: América y España',
        pregunta='¿En qué continentes se encuentran los colombianos detenidos?',
        variables='CONTINENTE (derivada de PAÍS PRISIÓN), CANTIDAD; CONSULADO para el '
                  'periodo sin país.',
        procedimiento='Asignación de cada país a su continente con el catálogo PAISES; '
                      'suma de CANTIDAD por continente; comparación entre el periodo con '
                      'país reportado y el periodo en que el país se infiere del '
                      'consulado.',
        evidencia='Gráfica K2 (continentes por periodo) de esta página; dona '
                  '"Participación de cada continente en el total global" del tablero.',
        hallazgo=(f"América concentra el <strong>{_p(c2['pct_america'])}</strong> de los "
                  f"detenidos con país identificado y Europa el "
                  f"<strong>{_p(c2['pct_europa'])}</strong>; Asia, África y Oceanía juntas "
                  f"apenas suman el {_p(c2['pct_resto'])}. Dentro de Europa, España aporta "
                  f"el <strong>{_p(c2['pct_espana_europa'])}</strong>.{despues}"),
        interpretacion='Tres de cada cuatro detenidos están en el mismo continente que '
                       'Colombia. El patrón coincide con la cercanía geográfica, los '
                       'flujos migratorios regionales y las rutas del narcotráfico; '
                       'Europa entra al mapa casi exclusivamente por España, el principal '
                       'destino migratorio colombiano fuera de América.',
        utilidad='Justifica priorizar la cooperación judicial regional (acuerdos con '
                 'países vecinos y de Centroamérica) y tratar a España como un frente '
                 'propio dentro de Europa.',
        limitacion='El continente se deriva del país, así que hereda sus vacíos. En el '
                    'periodo sin país, los consulados con jurisdicción en varios países '
                    '(por ejemplo, Acra o Varsovia) no se asignan.',
    )


def _conocimiento_3(c3):
    sobre = _lista([f"{p} ({v:.1f}%)" for p, v in c3['sobre_umbral'].items()])
    cerca = _lista([f"{p} ({v:.1f}%)" for p, v in c3['cerca_umbral'].items()])
    robo = _lista(c3['robo'])
    v = c3['pais_mas_violento']
    texto_cerca = f", y {cerca} queda justo por debajo" if cerca else ''
    narcos = _lista(c3['sobre_umbral'].index.tolist() + c3['cerca_umbral'].index.tolist())
    opacos_lista = c3['sin_dato'][c3['sin_dato'] > 25].index.tolist()
    if c3['pais_opaco'] and c3['pais_opaco'] not in opacos_lista:
        opacos_lista.append(c3['pais_opaco'])
    opacos = _lista(opacos_lista)
    texto_robo = (f" En {robo} el delito más frecuente no es el narcotráfico sino el "
                  f"<em>robo / hurto</em>." if robo else '')
    return dict(
        numero=3,
        titulo='Cada territorio tiene un perfil delictivo propio',
        pregunta='¿El delito por el que se detiene a los colombianos es el mismo en '
                 'todos los países?',
        variables='PAÍS PRISIÓN, DELITO y CANTIDAD.',
        procedimiento='Normalización del delito (incluye "No reporta – Confidencialidad" '
                      'y "Desconocido" como sin dato); tabla cruzada país × delito para '
                      'los diez países con más detenidos; porcentaje de cada delito '
                      'sobre el total del país; delito dominante excluyendo el sin dato.',
        evidencia='Gráfica K3 (mapa de calor país × delito) de esta página; gráfica '
                  '"Ciudades del territorio: participación y perfil delictivo" del '
                  'tablero con el filtro de continente.',
        hallazgo=(f"El narcotráfico pesa el {_p(c3['pct_narco_global'])} en el total, pero "
                  f"varía entre el {c3['rango_narco'][0]:.1f}% ({c3['rango_narco'][1]}) y "
                  f"el {c3['rango_narco'][2]:.1f}% ({c3['rango_narco'][3]}). Superan el "
                  f"{UMBRAL_NARCO:.0f}% {sobre}{texto_cerca}.{texto_robo} {v} tiene la "
                  f"mayor carga de delitos violentos ({c3['violentos'][v]:.1f}%), y en "
                  f"{c3['pais_opaco']} el {c3['pct_opaco']:.1f}% de los casos no reporta el "
                  f"delito."),
        interpretacion='El perfil penal depende del territorio: los países de tránsito '
                       'y destino de droga concentran el narcotráfico, mientras que en '
                       'el Cono Sur y México predominan los delitos contra el patrimonio. '
                       'Una sola estrategia consular para todos los países dejaría por '
                       'fuera estas diferencias.',
        utilidad=('Diseñar la defensa técnica y las campañas de prevención por país: '
                  f"derecho penal de drogas en {narcos}" +
                  (f"; delitos patrimoniales en {robo}" if robo else '') + '.'),
        limitacion=('El cruce solo es posible en los registros con país reportado. ' +
                    (f"{opacos} tienen una proporción alta de delito sin dato, que "
                     'puede cambiar el perfil real de esos países.' if opacos else '')),
    )


def _conocimiento_4(c4):
    sup = c4['capitales_superadas']
    limite = int(sup['PUESTO'].min()) if not sup.empty else 10**6
    front = c4['frontera'][c4['frontera']['PUESTO'] < limite]
    if front.empty:
        front = c4['frontera'].head(2)
    lista = _lista([f"{nombre_consulado(r.CONSULADO)} (puesto {r.PUESTO}, {r.PCT:.2f}%)"
                    for r in front.itertuples()])
    caps = _lista([f"{nombre_consulado(r.CONSULADO)} (puesto {r.PUESTO})"
                   for r in sup.itertuples()])
    detalle = []
    for pais, d in c4['por_pais'].items():
        detalle.append(f"en {pais} los consulados de frontera atienden el "
                       f"<strong>{_p(d['pct_frontera'])}</strong> de los detenidos del país "
                       f"frente al {_p(d['pct_capital'])} de {nombre_consulado(d['capital'])}")
    anual = c4['anual']
    return dict(
        numero=4,
        titulo='Los consulados de frontera tienen carga de capital',
        pregunta='¿Qué peso tienen las jurisdicciones consulares ubicadas en la frontera '
                 'con Colombia?',
        variables='CONSULADO, PAÍS PRISIÓN (o país inferido del consulado) y CANTIDAD.',
        procedimiento='Limpieza del nombre del consulado; ranking de consulados por suma '
                      'de CANTIDAD sobre la población total (sin la Asistencia Central de '
                      'Bogotá, que no es un territorio en el exterior); marcación de los consulados '
                      'de frontera (Tulcán, Esmeraldas, Nueva Loja, San Cristóbal, San '
                      'Antonio del Táchira y Maracaibo); comparación con las capitales y '
                      'peso de la frontera dentro de Ecuador y Venezuela.',
        evidencia='Gráfica K4 (top 20 consulados) de esta página; gráfica "Top 15 '
                  'jurisdicciones consulares" del tablero.',
        hallazgo=(f"Los seis consulados de frontera suman el "
                  f"<strong>{_p(c4['pct_frontera'])}</strong> de toda la población. "
                  f"{_mayuscula(lista)} " +
                  (f"{'superan' if len(front) > 1 else 'supera'} a capitales como {caps}"
                   if caps else 'son los de mayor carga') + ". " +
                  (_mayuscula('; '.join(detalle)) if detalle else '') +
                  f". Según el año, el peso de la frontera oscila entre el {anual.min():.1f}% "
                  f"({int(anual.idxmin())}) y el {anual.max():.1f}% ({int(anual.idxmax())})."),
        interpretacion='La frontera terrestre con Ecuador y Venezuela genera una carga '
                       'consular comparable a la de grandes capitales, pero con '
                       'consulados normalmente más pequeños. Es un comportamiento '
                       'propio de territorios limítrofes, donde el paso cotidiano y las '
                       'economías ilegales de frontera elevan las detenciones.',
        utilidad='Sustenta un plan específico para los consulados de frontera '
                 '(personal, defensoría y articulación con autoridades locales), en '
                 'lugar de asignar recursos solo según el tamaño de la ciudad.',
        limitacion='El consulado indica la jurisdicción que atiende el caso, no la '
                   'cárcel exacta. La lista de consulados de frontera es un criterio del '
                   'análisis y podría ampliarse (por ejemplo, Tabatinga o Iquitos).',
    )


def _conocimiento_5(c5):
    q = c5['anio_quiebre']
    return dict(
        numero=5,
        titulo='El país de prisión dejó de reportarse; el consulado lo sustituye',
        pregunta=('¿Por qué más de la mitad de la población aparece con país '
                  '"Desconocido" y se puede seguir haciendo análisis territorial?'),
        variables='PAÍS PRISIÓN, CONSULADO, FECHA PUBLICACIÓN y CANTIDAD.',
        procedimiento='Composición del dato territorial por año de publicación (país '
                      'reportado, extradición/repatriación, desconocido). Tabla '
                      'consulado → país con los registros que sí traen país y medida de '
                      f'pureza; se considera confiable cuando ≥ {PUREZA_CONSULADO:.0%} de '
                      'la población del consulado está en un mismo país.',
        evidencia='Gráfica K5 (composición anual del dato territorial) de esta página; '
                  'KPI "Sin país identificado" del tablero.',
        hallazgo=((f"El {_p(c5['pct_sin_pais_total'])} de la población no tiene país. No es "
                   f"un faltante al azar: en {c5['anio_inicio']} solo faltaba en el "
                   f"{_p(c5['pct_sin_pais_inicio'])}, creció hasta el {_p(c5['pct_sin_pais_previo'] or 0)} "
                   f"en {q - 1} y desde <strong>{q}</strong> ningún registro trae país. En "
                   f"cambio, el "
                   f"consulado viene diligenciado para el "
                   f"<strong>{_p(c5['pct_consulado_diligenciado'])}</strong>, y "
                   f"{c5['n_consulados_puros']} de {c5['n_consulados_con_pais']} consulados "
                   f"atienden un solo país. Con ellos se recupera el país del "
                   f"<strong>{_p(c5['pct_recuperado'])}</strong> de la población sin país, "
                   f"y la cobertura territorial sube al "
                   f"<strong>{_p(c5['pct_cobertura_final'])}</strong>.")
                  if q else
                  (f"El {_p(c5['pct_sin_pais_total'])} de la población no tiene país; el "
                   f"consulado permite recuperar el {_p(c5['pct_recuperado'])}.")),
        interpretacion='El vacío del país es un cambio en la forma de publicar los datos '
                       'a partir de un año concreto, no una pérdida aleatoria. Por eso el '
                       'consulado es el nivel territorial más completo del conjunto y el '
                       'que permite comparar el periodo reciente con el anterior.',
        utilidad='Justifica usar el consulado como respaldo del país en el tablero y '
                 'sustenta una solicitud a la Cancillería para que vuelva a publicar '
                 'PAÍS PRISIÓN en los cortes recientes.',
        limitacion='La inferencia supone que cada consulado mantuvo la misma '
                   'jurisdicción en todo el periodo. Los consulados con jurisdicción en '
                   'varios países y la Asistencia Central de Bogotá quedan sin país.',
    )


# ============================================================
# 5. CONTEXTO PARA LA PLANTILLA
# ============================================================

_CACHE = {}


def construir_contexto_analisis(df):
    """Calcula todo y devuelve el diccionario para analisis_territorial.html."""
    if _CACHE.get('origen') is df:
        return _CACHE['contexto']

    t, tabla = preparar_analisis(df)

    c5 = calcular_calidad_territorial(t, tabla)
    c1 = calcular_concentracion(t)
    c2 = calcular_continentes(t, c5['anio_quiebre'])
    c3 = calcular_perfil_delictivo(t)
    c4 = calcular_frontera(t)

    render = territorial._Renderizador()
    graficas = dict(
        grafica_k1=grafica_k1(c1, render),
        grafica_k2=grafica_k2(c2, render),
        grafica_k3=grafica_k3(c3, render),
        grafica_k4=grafica_k4(c4, render),
        grafica_k5=grafica_k5(c5, render),
    )

    conocimientos = [_conocimiento_1(c1), _conocimiento_2(c2), _conocimiento_3(c3),
                     _conocimiento_4(c4), _conocimiento_5(c5)]
    for k in conocimientos:
        k['grafica'] = graficas[f"grafica_k{k['numero']}"]

    top_consulados = [nombre_consulado(c) for c in c4['consulados'].head(4)['CONSULADO']]

    contexto = dict(
        # metodología
        total_registros=int(len(t)),
        poblacion_total=int(t['CANTIDAD'].sum()),
        n_cortes=int(t['FECHA'].nunique()),
        fecha_inicio=t['FECHA'].min().strftime('%d/%m/%Y'),
        fecha_fin=t['FECHA'].max().strftime('%d/%m/%Y'),
        n_paises=c1['n_paises'],
        n_consulados=c5['n_consulados'],
        # KPIs
        pct_top5=c1['pct_top5'],
        pct_america=c2['pct_america'],
        pct_frontera=c4['pct_frontera'],
        pct_cobertura_final=c5['pct_cobertura_final'],
        pct_sin_pais=c5['pct_sin_pais_total'],
        anio_quiebre=c5['anio_quiebre'],
        # conocimientos
        conocimientos=conocimientos,
        # decisiones
        top_paises=_lista(c1['top5']['PAIS'].tolist()),
        top_consulados=_lista(top_consulados),
        paises_narco=_lista(c3['sobre_umbral'].index.tolist() + c3['cerca_umbral'].index.tolist()),
        paises_robo=_lista(c3['robo']),
        consulados_frontera=_lista([nombre_consulado(c) for c in c4['frontera']['CONSULADO']]),
    )
    _CACHE['origen'] = df
    _CACHE['contexto'] = contexto
    return contexto


# ============================================================
# 6. EJECUCIÓN COMO SCRIPT
# ============================================================

def _cargar_csv():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ruta = os.path.join(base, 'data', 'Colombianos_detenidos_en_el_exterior.csv')
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No existe el archivo:\n{ruta}")
    try:
        df = pd.read_csv(ruta, encoding='utf-8', low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(ruta, encoding='latin-1', low_memory=False)
    return df, os.path.join(base, 'data', 'analisis_territorial')


def _texto_plano(html):
    import re
    return re.sub(r'<[^>]+>', '', html)


def main():
    df, salida = _cargar_csv()
    os.makedirs(salida, exist_ok=True)

    t, tabla = preparar_analisis(df)
    c5 = calcular_calidad_territorial(t, tabla)
    c1 = calcular_concentracion(t)
    c2 = calcular_continentes(t, c5['anio_quiebre'])
    c3 = calcular_perfil_delictivo(t)
    c4 = calcular_frontera(t)

    linea = '=' * 70
    print(linea)
    print('ANÁLISIS DE LA DIMENSIÓN TERRITORIAL — CONOCIMIENTOS EVIDENTES')
    print(linea)
    print(f"Registros: {len(t):,}  ·  Población (suma de CANTIDAD): {_f(t['CANTIDAD'].sum())}")
    print(f"Cortes de publicación: {t['FECHA'].nunique()} "
          f"({t['FECHA'].min():%d/%m/%Y} a {t['FECHA'].max():%d/%m/%Y})")

    for k in (_conocimiento_1(c1), _conocimiento_2(c2), _conocimiento_3(c3),
              _conocimiento_4(c4), _conocimiento_5(c5)):
        print('\n' + linea)
        print(f"CONOCIMIENTO {k['numero']} — {k['titulo'].upper()}")
        print(linea)
        for campo in ('pregunta', 'variables', 'procedimiento', 'evidencia', 'hallazgo',
                      'interpretacion', 'utilidad', 'limitacion'):
            print(f"\n{campo.upper()}:\n  {_texto_plano(k[campo])}")

    # ---------- tablas de soporte ----------
    exportar = {
        'k1_paises.csv': c1['paises'],
        'k1_paises_con_consulado.csv': c1['final'],
        'k2_continentes.csv': c2['continentes'],
        'k2_continentes_por_periodo.csv': c2['periodos'],
        'k3_perfil_delictivo_pais.csv': c3['matriz'].round(2).reset_index(),
        'k4_consulados.csv': c4['consulados'],
        'k5_calidad_territorial_anual.csv': c5['anual'].round(2),
        'tabla_consulado_pais.csv': tabla.reset_index(),
    }
    for nombre, tabla_out in exportar.items():
        tabla_out.to_csv(os.path.join(salida, nombre), index=False, encoding='utf-8-sig')

    # ---------- gráficas ----------
    render = territorial._Renderizador()
    render.primera = False          # plotly.js se añade a mano en cada archivo
    for i, (funcion, datos) in enumerate(((grafica_k1, c1), (grafica_k2, c2),
                                          (grafica_k3, c3), (grafica_k4, c4),
                                          (grafica_k5, c5)), start=1):
        html = funcion(datos, render)
        with open(os.path.join(salida, f"grafica_k{i}.html"), 'w', encoding='utf-8') as fh:
            fh.write('<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>\n'
                     + html)

    print('\n' + linea)
    print('ANÁLISIS FINALIZADO')
    print(linea)
    print('Resultados guardados en:', salida)


if __name__ == '__main__':
    sys.exit(main())
