import os
import json
import pandas as pd
import geopandas as gpd
from shapely import wkb
from dash import Dash, dcc, html, Input, Output
import plotly.express as px

print("======== INICIO APP ========")

app = Dash(__name__, suppress_callback_exceptions=True)
server = app.server  
# Procesamiento de datos geográficos y estadísticos

# Leer shapefile y CSV
gdf = gpd.read_file("MGN_MPIO_POLITICO.shp", encoding='utf-8')
df = pd.read_csv("ventas.csv")

# Crear código DANE completo
gdf["DANE_COMPLETO"] = gdf["DPTO_CCDGO"].astype(str).str.zfill(2) + gdf["MPIO_CCDGO"].astype(str).str.zfill(3)
df["CODIGO_MUNICIPIO_DANE"] = df["CODIGO_MUNICIPIO_DANE"].astype(str).str.zfill(5)

# Unir datos geográficos con los datos de ventas
merged = gdf.merge(df, left_on="DANE_COMPLETO", right_on="CODIGO_MUNICIPIO_DANE")

# Agregación por departamento
df_dep = merged.groupby("DPTO_CNMBR").agg({
    "CANTIDAD_VOLUMEN_SUMINISTRADO": "sum",
    "VEHICULOS_ATENDIDOS": "sum",
    "NUMERO_DE_VENTAS": "sum",
    "EDS_ACTIVAS": "sum"
}).reset_index()

df_dep["VOLUMEN_POR_EDS"] = df_dep["CANTIDAD_VOLUMEN_SUMINISTRADO"] / df_dep["EDS_ACTIVAS"]

# Crear geometría por departamento
gdf_departamentos = gdf.dissolve(by="DPTO_CNMBR", as_index=False)

# Unir geometría con datos agregados
mapa_dep = gdf_departamentos.merge(df_dep, on="DPTO_CNMBR")

# Crear columnas en millones
mapa_dep["VOLUMEN_MILLONES"] = mapa_dep["CANTIDAD_VOLUMEN_SUMINISTRADO"] / 1e6
mapa_dep["VEHICULOS_MILLONES"] = mapa_dep["VEHICULOS_ATENDIDOS"] / 1e6
mapa_dep["VENTAS_MILLONES"] = mapa_dep["NUMERO_DE_VENTAS"] / 1e6

# Simplificación para el mapa
gdf_geo = mapa_dep[["DPTO_CNMBR", "geometry"]].copy()
gdf_geo["geometry"] = gdf_geo.simplify(tolerance=0.01, preserve_topology=True)

# Diccionario de variables para visualización
variables = {
    "VOLUMEN_MILLONES": "Volumen suministrado (millones m³)",
    "VENTAS_MILLONES": "Número de ventas (millones)",
    "VEHICULOS_MILLONES": "Vehículos atendidos (millones)",
    "VOLUMEN_POR_EDS": "Volumen promedio por EDS (m³)"
}

# Crear app Dash
app = Dash(__name__, server=server, suppress_callback_exceptions=True)
server = app.server
print("======== APP CREADA ========")

# Estilo dark mode
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            html, body {
                background-color: #141627;
                color: white;
                margin: 0;
                padding: 0;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Layout principal
app.layout = html.Div([
    html.H1("Dashboard de Consumo de Gas Vehicular", style={"textAlign": "center", "color": "white"}),

    dcc.Tabs(id="tabs", value='mapa', children=[
        dcc.Tab(label='Contexto del problema', value='contexto', style={"backgroundColor": "#2c2e4a", "color": "white"}, selected_style={"backgroundColor": "#4c4f75", "color": "white"}),
        dcc.Tab(label='Mapa Interactivo', value='mapa', style={"backgroundColor": "#2c2e4a", "color": "white"}, selected_style={"backgroundColor": "#4c4f75", "color": "white"}),
        dcc.Tab(label='Análisis Gráfico', value='graficos', style={"backgroundColor": "#2c2e4a", "color": "white"}, selected_style={"backgroundColor": "#4c4f75", "color": "white"}),
        dcc.Tab(label='Tabla Comparativa', value='tabla', style={"backgroundColor": "#2c2e4a", "color": "white"}, selected_style={"backgroundColor": "#4c4f75", "color": "white"}),
    ]),

    dcc.Store(id="stored-variable", data="VOLUMEN_MILLONES"),
    html.Div(id='contenido-tab', style={"padding": "20px"})
], style={"backgroundColor": "#141627", "fontFamily": "Arial"})

# Callbacks
@app.callback(
    Output("contenido-tab", "children"),
    Input("tabs", "value")
)
def render_tab(tab):
    if tab == 'mapa':
        return html.Div([
            html.Div([
                html.Label("Selecciona una variable:", style={"color": "white", "fontSize": "18px", "marginBottom": "10px"}),
                dcc.RadioItems(
                    id="variable",
                    options=[{"label": label, "value": var} for var, label in variables.items()],
                    value="VOLUMEN_MILLONES",
                    labelStyle={
                        "display": "block",
                        "color": "white",
                        "fontSize": "16px",
                        "marginBottom": "10px"
                    },
                    inputStyle={
                        "marginRight": "10px",
                        "width": "20px",
                        "height": "20px",
                        "accentColor": "limegreen"
                    }
                )
            ], style={"width": "20%", "padding": "20px"}),

            html.Div([
                dcc.Graph(id="mapa")
            ], style={"width": "75%", "display": "inline-block"})
        ], style={"display": "flex", "alignItems": "center"})

    elif tab == 'graficos':
        fig2 = px.bar(mapa_dep.sort_values("VOLUMEN_MILLONES", ascending=False).head(10), x="DPTO_CNMBR", y="VOLUMEN_MILLONES", title="Top 10 departamentos por volumen", color_discrete_sequence=["orange"])
        fig3 = px.bar(mapa_dep.sort_values("VEHICULOS_MILLONES", ascending=False).head(10), x="DPTO_CNMBR", y="VEHICULOS_MILLONES", title="Top 10 departamentos por vehículos", color_discrete_sequence=["purple"])

        for fig in [fig2, fig3]:
            fig.update_layout(paper_bgcolor="#141627", plot_bgcolor="#141627", font_color="white")

        return html.Div([
            dcc.Graph(figure=fig2),
            dcc.Graph(figure=fig3)
        ])

    elif tab == 'tabla':
        resumen = mapa_dep[["DPTO_CNMBR", "VOLUMEN_MILLONES", "VENTAS_MILLONES", "VEHICULOS_MILLONES", "VOLUMEN_POR_EDS"]].round(2).sort_values("VOLUMEN_MILLONES", ascending=False).head(10)
        return html.Div([
            html.H4("Top 10 departamentos por volumen suministrado", style={"color": "white"}),
            html.Table([
                html.Thead([html.Tr([html.Th(col, style={"color": "white", "border": "1px solid white"}) for col in resumen.columns])]),
                html.Tbody([
                    html.Tr([html.Td(resumen.iloc[i][col], style={"color": "white", "border": "1px solid white"}) for col in resumen.columns]) for i in range(len(resumen))
                ])
            ], style={"width": "100%", "borderCollapse": "collapse"})
        ])
        
    elif tab == 'contexto':
        return html.Div([
            html.Div([
                html.H3("Contexto del problema", style={"color": "white"}),
                html.P("En Colombia, el gas natural vehicular (GNV) se ha convertido en una alternativa económica "
                    "y ambientalmente sostenible frente a otros combustibles. Sin embargo, su consumo varía significativamente "
                    "entre los departamentos. Este dashboard permite visualizar el comportamiento del GNV en todo el país durante "
                    "el último año disponible, analizando variables como el volumen suministrado, ventas, número de vehículos "
                    "atendidos y eficiencia por estación.",
                       style={"color": "white", "textAlign": "justify", "fontSize": "16px"})
            ], style={"width": "60%", "padding": "30px"}),

            html.Div([
                html.Img(src="/assets/Gasoline.png", style={
                    "width": "100%",
                    "maxWidth": "300px",
                    "margin": "auto",
                    "display": "block",
                    "boxShadow": "0px 0px 30px red",
                    "borderRadius": "20px"
                })
            ], style={"width": "40%", "display": "flex", "justifyContent": "center", "alignItems": "center", "padding": "30px"})
        ],
        style={"display": "flex", "backgroundColor": "#141627", "flexDirection": "row"})

@app.callback(
    Output("stored-variable", "data"),
    Input("variable", "value")
)
def guardar_variable(variable):
    return variable

@app.callback(
    Output("mapa", "figure"),
    Input("stored-variable", "data")
)
def actualizar_mapa(variable):
    fig = px.choropleth(
        mapa_dep,
        geojson=json.loads(gdf_geo.to_json()),
        locations="DPTO_CNMBR",
        featureidkey="properties.DPTO_CNMBR",
        color=variable,
        projection="mercator",
        color_continuous_scale="Viridis",
        labels={variable: variables[variable]},
        hover_name="DPTO_CNMBR"
    )

    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, paper_bgcolor="#141627", plot_bgcolor="#141627", font_color="white")
    
    return fig

if __name__ == '__main__':
    app.run(debug=True)
