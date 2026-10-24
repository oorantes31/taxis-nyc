"""Parte 2 · Segmentación de zonas con K-Means y PCA (precalculada en el notebook)."""
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from comun import (AZUL, SIMBOLOS, badge_grupo, color_grupo, leer_csv, leer_json, orden_grupos,
                   zonas_segmentadas)

st.title("Tipos de zona")
st.markdown("No se planifica igual un aeropuerto que una zona de bares. Agrupamos las zonas según **cómo se usan** "
            "(volumen, distancia, tarifa, horario y fin de semana) con K-Means, y las dibujamos en dos ejes con PCA.")

zonas = zonas_segmentadas()
meta = leer_json("meta_segmentacion.json")
silueta = leer_csv("silueta.csv")
grupos = orden_grupos()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Zonas segmentadas", f"{len(zonas)}", help="Zonas con al menos 500 viajes en enero 2024", border=True)
m2.metric("Tipos de zona (k)", meta["k"], border=True)
m3.metric("Silueta del k elegido", f"{silueta.loc[silueta['k'] == meta['k'], 'silueta'].iloc[0]:.2f}", border=True,
          chart_data=silueta["silueta"].round(3).tolist(), chart_type="line",
          help="Mini gráfico: silueta para k = 2 a 7")
m4.metric("Variación que conserva PCA", f"{sum(meta['varianza_pca']):.0%}",
          help=f"PC1 {meta['varianza_pca'][0]:.0%} + PC2 {meta['varianza_pca'][1]:.0%}", border=True)

with st.expander("¿Por qué estos grupos? Silueta y componentes", icon=":material/help:"):
    c1, c2 = st.columns(2)
    with c1:
        fig_s = go.Figure(go.Scatter(x=silueta["k"], y=silueta["silueta"], mode="lines+markers",
                                     line=dict(color=AZUL, width=2), marker=dict(size=9),
                                     hovertemplate="k = %{x}<br>silueta = %{y:.3f}<extra></extra>"))
        fig_s.add_vline(x=meta["k"], line_dash="dash", line_color="#eb6834", annotation_text=f"k elegido = {meta['k']}")
        fig_s.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="Número de grupos (k)",
                            yaxis_title="Coeficiente de silueta", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_s, width="stretch")
    with c2:
        st.markdown(
            "- **Silueta** (de −1 a 1): qué tan cerca está cada zona de su grupo frente al grupo vecino. "
            f"Probamos k = 2 a 7 y elegimos **k = {meta['k']}**, el de **mayor silueta**.\n"
            "- Las variables se **escalaron** con `StandardScaler` antes de K-Means, para que ninguna domine por su unidad.\n"
            f"- **PCA** resume las 8 variables en 2 ejes que conservan el {sum(meta['varianza_pca']):.0%} de la variación. "
            "Los nombres de los grupos salen de su perfil (p. ej. 'el de mayor distancia mediana = aeropuertos'), no de su número."
        )
        st.dataframe(leer_json("meta_segmentacion.json")["cargas_pca"], width="stretch")

with st.expander("¿Qué variables distinguen a cada grupo?", icon=":material/grid_on:"):
    ETIQ = {"log_viajes_dia": "Volumen de viajes", "distancia_mediana": "Distancia", "tarifa_mediana": "Tarifa",
            "propina_mediana": "Propina", "pct_fin_semana": "% fin de semana", "pct_manana": "% 6–10 h",
            "pct_tarde": "% 16–20 h", "pct_noche": "% 22–5 h"}
    vars_seg = meta["variables"]
    escaladas = (zonas[vars_seg] - zonas[vars_seg].mean()) / zonas[vars_seg].std(ddof=0)  # igual que StandardScaler
    z_grupo = escaladas.groupby(zonas["grupo"]).mean().reindex(grupos)
    fig_z = go.Figure(go.Heatmap(
        z=z_grupo.values, x=[ETIQ.get(v, v) for v in vars_seg], y=list(z_grupo.index), colorscale="RdBu", zmid=0,
        zmin=-2.5, zmax=2.5, text=np.round(z_grupo.values, 1), texttemplate="%{text:+.1f}",
        hovertemplate="%{y}<br>%{x}: %{z:+.2f} desv. estándar<extra></extra>",
        colorbar=dict(title="Desv.<br>estándar")))
    fig_z.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_z, width="stretch")
    separacion = z_grupo.abs().max().sort_values(ascending=False)
    st.caption("Cada celda dice cuántas desviaciones estándar se aleja el promedio del grupo del promedio de todas las zonas, "
               "con las mismas variables escaladas que usó K-Means. Azul = más que el promedio; rojo = menos. "
               "Las variables que más separan a los grupos son: "
               + ", ".join(f"**{ETIQ.get(v, v)}**" for v in separacion.index[:3]) + ".")

# ----- Tarjetas de los grupos -----
cols = st.columns(len(grupos))
for col, g in zip(cols, grupos):
    sub = zonas[zonas["grupo"] == g]
    with col.container(border=True):
        badge_grupo(g)
        st.markdown(f"**{len(sub)} zonas** · {sub['viajes_dia'].sum():,.0f} viajes/día")
        st.caption(meta["grupos"][g]["descripcion"])
        st.caption(f"Distancia mediana {sub['distancia_mediana'].median():.1f} mi · tarifa US\\${sub['tarifa_mediana'].median():.0f}")

# ----- Filtros -----
elegidos = st.pills("Grupos", grupos, selection_mode="multi", default=grupos)
distritos = sorted(zonas["distrito"].dropna().unique())
dist_sel = st.multiselect("Distrito", distritos, placeholder="Todos los distritos")
vista = zonas[zonas["grupo"].isin(elegidos or [])]
if dist_sel:
    vista = vista[vista["distrito"].isin(dist_sel)]

# ----- Mapa PCA con selección -----
izq, der = st.columns([3, 2])
with izq:
    fig = px.scatter(
        vista, x="pc1", y="pc2", color="grupo", symbol="grupo", custom_data=["zona_id"],
        category_orders={"grupo": grupos}, color_discrete_map={g: color_grupo(g) for g in grupos},
        symbol_map={g: SIMBOLOS[i % len(SIMBOLOS)] for i, g in enumerate(grupos)},
        hover_name="nombre", hover_data={"distrito": True, "viajes_dia": ":,.0f", "distancia_mediana": ":.1f",
                                         "pc1": False, "pc2": False, "grupo": False, "zona_id": True},
        labels={"pc1": f"PC1 ({meta['varianza_pca'][0]:.0%} de la variación)",
                "pc2": f"PC2 ({meta['varianza_pca'][1]:.0%})", "grupo": "Tipo de zona",
                "viajes_dia": "Viajes/día", "distancia_mediana": "Distancia mediana (mi)", "zona_id": "ID"},
    )
    fig.update_traces(marker=dict(size=10, line=dict(color="white", width=1.5)))
    fig.update_layout(height=470, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=1.08, x=0, title=None),
                      plot_bgcolor="rgba(0,0,0,0)", dragmode="lasso")
    fig.update_xaxes(gridcolor="rgba(0,0,0,0.08)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0.08)", zeroline=False)
    evento = st.plotly_chart(fig, width="stretch", on_select="rerun",
                             selection_mode=("points", "box", "lasso"), key="mapa_pca")
    st.caption("Haz clic en una zona, o usa el lazo / rectángulo para seleccionar varias.")

ids_sel = []
if evento and evento.selection and evento.selection.points:
    ids_sel = [p["customdata"][0] for p in evento.selection.points if p.get("customdata")]
seleccion = vista[vista["zona_id"].isin(ids_sel)] if ids_sel else vista

with der:
    if len(ids_sel) == 1:
        z = seleccion.iloc[0]
        with st.container(border=True):
            st.subheader(z["nombre"])
            badge_grupo(z["grupo"])
            st.caption(f"{z['distrito']} · zona #{z['zona_id']}")
            a, b = st.columns(2)
            a.metric("Viajes por día", f"{z['viajes_dia']:,.0f}")
            b.metric("Distancia mediana", f"{z['distancia_mediana']:.1f} mi")
            a.metric("Tarifa mediana", f"${z['tarifa_mediana']:.0f}")
            b.metric("En fin de semana", f"{z['pct_fin_semana']:.0%}")
            st.bar_chart({"Proporción de viajes": z["perfil_horario"]}, height=150, color=color_grupo(z["grupo"]))
            st.caption("Proporción de viajes en cada hora del día (0 a 23 h)")
            if z["pronosticable"]:
                if st.button("Ver el pronóstico de esta zona", icon=":material/insights:", width="stretch"):
                    st.session_state["zona_id"] = int(z["zona_id"])
                    st.switch_page("paginas/pronostico.py")
            else:
                st.caption(":material/info: Esta zona tiene menos de 3,000 viajes al mes y no se pronostica.")
    else:
        with st.container(border=True):
            titulo = f"{len(seleccion)} zonas seleccionadas" if ids_sel else f"{len(seleccion)} zonas en el filtro"
            st.subheader(titulo)
            resumen = seleccion.groupby("grupo").agg(zonas=("zona_id", "size"), viajes_dia=("viajes_dia", "sum"))
            for g, r in resumen.iterrows():
                st.markdown(f"<span style='color:{color_grupo(g)}'>●</span> **{g}**: {int(r['zonas'])} zonas · "
                            f"{r['viajes_dia']:,.0f} viajes/día", unsafe_allow_html=True)
            if not ids_sel:
                st.caption("Selecciona zonas en el gráfico para ver su detalle.")

# ----- Tabla -----
st.subheader("Detalle de las zonas")
tabla = seleccion.sort_values("viajes_dia", ascending=False)[
    ["zona_id", "nombre", "distrito", "grupo", "viajes_dia", "distancia_mediana", "tarifa_mediana",
     "pct_fin_semana", "pct_noche", "perfil_horario"]]
st.dataframe(
    tabla, hide_index=True, width="stretch", height=380,
    column_config={
        "zona_id": st.column_config.NumberColumn("ID", format="%d"),
        "nombre": "Zona", "distrito": "Distrito", "grupo": "Tipo de zona",
        "viajes_dia": st.column_config.ProgressColumn("Viajes/día", format="%.0f", min_value=0,
                                                      max_value=float(zonas["viajes_dia"].max())),
        "distancia_mediana": st.column_config.NumberColumn("Distancia (mi)", format="%.1f"),
        "tarifa_mediana": st.column_config.NumberColumn("Tarifa", format="$%.0f"),
        "pct_fin_semana": st.column_config.NumberColumn("% fin de semana", format="percent"),
        "pct_noche": st.column_config.NumberColumn("% 22–5 h", format="percent"),
        "perfil_horario": st.column_config.LineChartColumn("Viajes por hora (0–23 h)", y_min=0),
    },
)
