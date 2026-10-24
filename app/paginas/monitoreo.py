"""Extra · Monitoreo: error del modelo día a día en la semana de prueba, con alerta al pasar un límite."""
import plotly.graph_objects as go
import streamlit as st

from comun import AZUL, GRIS, fecha_corta, leer_csv, zonas_segmentadas

st.title("Monitoreo del error")
st.markdown("Un modelo en producción hay que **vigilarlo**: si el error sube de golpe, algo cambió (clima, un evento, "
            "un cambio en los datos) y no se debe confiar a ciegas en la recomendación. Aquí medimos el error de cada día "
            "de la semana de prueba y avisamos cuando pasa el límite que fijes.")

diario = leer_csv("error_diario_zona.csv")
zonas = zonas_segmentadas()[["zona_id", "nombre", "distrito", "grupo"]]
diario = diario.merge(zonas, left_on="PULocationID", right_on="zona_id", how="left")

c1, c2, c3 = st.columns([1.6, 1.6, 1.2], vertical_alignment="bottom")
nivel = c1.segmented_control("Ver", ["Toda la ciudad", "Tipo de zona", "Una zona"], default="Toda la ciudad")
nivel = nivel or "Toda la ciudad"
if nivel == "Tipo de zona":
    grupo = c2.selectbox("Tipo de zona", sorted(diario["grupo"].dropna().unique()))
    sub = diario[diario["grupo"] == grupo]
    etiqueta = grupo
elif nivel == "Una zona":
    opciones = diario[["PULocationID", "nombre"]].drop_duplicates().sort_values("nombre")
    zona_def = st.session_state.get("zona_id", 161)
    ids = opciones["PULocationID"].tolist()
    zona = c2.selectbox("Zona", ids, index=ids.index(zona_def) if zona_def in ids else 0,
                        format_func=dict(zip(opciones["PULocationID"], opciones["nombre"])).get)
    sub = diario[diario["PULocationID"] == zona]
    etiqueta = opciones.set_index("PULocationID").loc[zona, "nombre"]
else:
    sub = diario
    etiqueta = "toda la ciudad"
limite = c3.slider("Límite de alerta (WAPE)", min_value=0.05, max_value=0.60, value=0.20, step=0.01, format="%.2f",
                   help="WAPE = error absoluto total del día / viajes reales del día. Si un día lo supera, se alerta.")

por_dia = sub.groupby("fecha").agg(real=("real", "sum"), err_modelo=("err_modelo", "sum"),
                                   err_semana=("err_semana", "sum"), cobertura=("cobertura_80", "mean")).reset_index()
por_dia["WAPE_modelo"] = por_dia["err_modelo"] / por_dia["real"].clip(lower=1)
por_dia["WAPE_semana"] = por_dia["err_semana"] / por_dia["real"].clip(lower=1)
por_dia["alerta"] = por_dia["WAPE_modelo"] > limite
por_dia["dia"] = por_dia["fecha"].map(fecha_corta)

alertas = por_dia[por_dia["alerta"]]
m1, m2, m3 = st.columns(3)
m1.metric(f"WAPE de la semana · {etiqueta}", f"{por_dia['err_modelo'].sum() / max(por_dia['real'].sum(), 1):.1%}",
          border=True, chart_data=por_dia["WAPE_modelo"].round(4).tolist(), chart_type="line")
m2.metric("Días sobre el límite", f"{len(alertas)} de {len(por_dia)}", border=True)
m3.metric("Cobertura promedio del rango 80%", f"{por_dia['cobertura'].mean():.0%}", border=True)

if len(alertas):
    dias_txt = ", ".join(alertas["dia"])
    st.error(f"**Alerta:** el error pasó el límite de {limite:.0%} en: **{dias_txt}**. Revisa qué pasó esos días "
             "(clima, eventos, datos) antes de usar la recomendación sin supervisión.", icon=":material/notification_important:")
    clave = (etiqueta, round(limite, 2), len(alertas))
    if st.session_state.get("ultima_alerta") != clave:
        st.session_state["ultima_alerta"] = clave
        st.toast(f"{len(alertas)} día(s) superan el límite de error", icon=":material/warning:")
else:
    st.success(f"Ningún día pasó el límite de {limite:.0%}. El modelo se comportó dentro de lo esperado.",
               icon=":material/check_circle:")

colores = ["#e34948" if a else AZUL for a in por_dia["alerta"]]
fig = go.Figure()
fig.add_trace(go.Bar(x=por_dia["dia"], y=por_dia["WAPE_modelo"], name="Error del modelo (WAPE)",
                     marker=dict(color=colores, cornerradius=4),
                     text=["⚠" if a else "" for a in por_dia["alerta"]], textposition="outside",
                     hovertemplate="%{x}: %{y:.1%}<extra>Modelo</extra>"))
fig.add_trace(go.Scatter(x=por_dia["dia"], y=por_dia["WAPE_semana"], mode="lines+markers", name="Regla 'hace una semana'",
                         line=dict(color=GRIS, width=2, dash="dot"), marker=dict(size=8),
                         hovertemplate="%{x}: %{y:.1%}<extra>Hace una semana</extra>"))
fig.add_hline(y=limite, line_dash="dash", line_color="#e34948", annotation_text=f"Límite {limite:.0%}",
              annotation_position="top left")
fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), yaxis=dict(tickformat=".0%", title="WAPE"),
                  legend=dict(orientation="h", y=1.1, x=0), plot_bgcolor="rgba(0,0,0,0)")
fig.update_yaxes(gridcolor="rgba(0,0,0,0.08)")
st.plotly_chart(fig, width="stretch")
st.caption("Barras rojas con ⚠ = días que superan el límite. La línea gris es el error de la regla simple, como referencia.")

if nivel != "Una zona":
    st.subheader("Zonas que más pasaron el límite")
    zd = sub.assign(WAPE=sub["err_modelo"] / sub["real"].clip(lower=1))
    zd["sobre_limite"] = zd["WAPE"] > limite
    ranking = (zd.groupby(["nombre", "distrito", "grupo"])
               .agg(dias_sobre_limite=("sobre_limite", "sum"), WAPE_max=("WAPE", "max"), viajes=("real", "sum"),
                    serie=("WAPE", list)).reset_index()
               .sort_values(["dias_sobre_limite", "WAPE_max"], ascending=False).head(15))
    st.dataframe(ranking, hide_index=True, width="stretch",
                 column_config={"nombre": "Zona", "distrito": "Distrito", "grupo": "Tipo de zona",
                                "dias_sobre_limite": st.column_config.ProgressColumn("Días sobre el límite", format="%d",
                                                                                     min_value=0, max_value=7),
                                "WAPE_max": st.column_config.NumberColumn("Peor día (WAPE)", format="percent"),
                                "viajes": st.column_config.NumberColumn("Viajes en la semana", format="%d"),
                                "serie": st.column_config.LineChartColumn("WAPE diario (25→31 ene)", y_min=0)})

st.caption("Las cifras salen del notebook `preparacion.ipynb` (archivo `app/data/error_diario_zona.csv`).")
