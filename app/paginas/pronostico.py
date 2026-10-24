"""Parte 1 · Pronóstico de viajes por hora con su banda de incertidumbre (datos desde la API)."""
import plotly.graph_objects as go
import streamlit as st

from comun import (AZUL, GRIS, ErrorAPI, badge_grupo, cargar_info, fecha_corta, grupo_de_zona,
                   mostrar_error_api, pronostico, selector_zona_fecha)


@st.dialog("¿Cómo leer este pronóstico?", width="large")
def ayuda():
    st.markdown(
        """
- **La línea azul** es la *mediana* (p50): la cantidad de viajes más probable en esa hora.
  La mitad de las veces habrá más y la otra mitad menos.
- **La banda celeste** va del cuantil 10% al 90%: en 8 de cada 10 horas los viajes reales
  deberían caer dentro de ella. Mientras más ancha, más incertidumbre.
- **Los puntos negros** son los viajes que de verdad ocurrieron (solo del 25 al 31 de enero).
- **La línea gris punteada** es lo que pasó a la misma hora hace una semana: la regla simple
  contra la que comparamos el modelo.
- El **1 de febrero** es "mañana": todavía no tiene datos reales, por eso solo verás el pronóstico.

El pronóstico se hace el día anterior para todo el día siguiente; usa los viajes de ayer, de anteayer y
de hace una semana, además de la hora, el día de la semana y si es feriado.
        """
    )


encabezado, boton = st.columns([5, 1], vertical_alignment="bottom")
encabezado.title("Pronóstico de viajes por hora")
if boton.button("Cómo leerlo", icon=":material/help:", width="stretch"):
    ayuda()

info = cargar_info()
zona_id, fecha = selector_zona_fecha(info, clave="pron")

try:
    with st.spinner("Pidiendo el pronóstico a la API…"):
        df = pronostico(zona_id, fecha)
except ErrorAPI as e:
    mostrar_error_api(e)

zona = df.attrs["zona"]
tiene_real = bool(df.attrs["tiene_real"])
grupo = grupo_de_zona(zona_id)

c1, c2 = st.columns([4, 2], vertical_alignment="center")
c1.subheader(f"{zona['nombre']} · {fecha_corta(fecha)}")
with c2:
    if grupo:
        badge_grupo(grupo)

if not tiene_real:
    st.info("Este día es **mañana**: aún no hay viajes reales para comparar. Se muestra solo el pronóstico con su rango.",
            icon=":material/event_upcoming:")

# ----- Métricas -----
total_p50 = df["p50"].sum()
total_semana = df["hace_una_semana"].sum()
pico = df.loc[df["p50"].idxmax()]
m1, m2, m3, m4 = st.columns(4)
m1.metric("Viajes esperados en el día (p50)", f"{total_p50:,.0f}",
          delta=f"{total_p50 - total_semana:+,.0f} vs hace una semana", delta_color="off",
          border=True, chart_data=df["p50"].round(1).tolist(), chart_type="area")
m2.metric("Hora pico esperada", f"{int(pico['hora']):02d}:00", delta=f"{pico['p50']:,.0f} viajes", delta_color="off",
          border=True)
m3.metric("Rango 80% del día", f"{df['p10'].sum() / 1000:.1f}k – {df['p90'].sum() / 1000:.1f}k",
          delta=f"{df['p10'].sum():,.0f} a {df['p90'].sum():,.0f} viajes", delta_color="off",
          help="Suma de los cuantiles 10% y 90% de cada hora.", border=True)
if tiene_real:
    total_real = df["real"].sum()
    error_pct = (total_p50 - total_real) / total_real if total_real else 0
    m4.metric("Viajes reales", f"{total_real:,.0f}", delta=f"{error_pct:+.1%} error del p50", delta_color="off",
              border=True, chart_data=df["real"].tolist(), chart_type="bar")
else:
    m4.metric("Viajes reales", "Sin datos", delta="Es mañana", delta_color="off", border=True)

# ----- Gráfico con banda de incertidumbre -----
etiqueta_hora = [f"{h:02d}:00" for h in df["hora"]]
fig = go.Figure()
fig.add_trace(go.Scatter(x=etiqueta_hora, y=df["p90"], mode="lines", line=dict(width=0), name="p90",
                         hovertemplate="p90: %{y:.0f}<extra></extra>", showlegend=False))
fig.add_trace(go.Scatter(x=etiqueta_hora, y=df["p10"], mode="lines", line=dict(width=0), fill="tonexty",
                         fillcolor="rgba(42,120,214,0.18)", name="Rango 80% (p10–p90)",
                         hovertemplate="p10: %{y:.0f}<extra></extra>"))
fig.add_trace(go.Scatter(x=etiqueta_hora, y=df["p50"], mode="lines", line=dict(color=AZUL, width=2),
                         name="Pronóstico (mediana)", hovertemplate="p50: %{y:.0f}<extra></extra>"))
fig.add_trace(go.Scatter(x=etiqueta_hora, y=df["hace_una_semana"], mode="lines", line=dict(color=GRIS, width=2, dash="dot"),
                         name="Hace una semana", hovertemplate="Hace una semana: %{y:.0f}<extra></extra>"))
if tiene_real:
    fig.add_trace(go.Scatter(x=etiqueta_hora, y=df["real"], mode="markers", marker=dict(color="#0b0b0b", size=8,
                             line=dict(color="white", width=2)), name="Real", hovertemplate="Real: %{y:.0f}<extra></extra>"))
fig.update_layout(height=420, margin=dict(l=10, r=10, t=30, b=10), hovermode="x unified",
                  legend=dict(orientation="h", y=1.08, x=0), yaxis_title="Viajes por hora",
                  plot_bgcolor="rgba(0,0,0,0)")
fig.update_yaxes(gridcolor="rgba(0,0,0,0.08)", rangemode="tozero")
fig.update_xaxes(showgrid=False)
st.plotly_chart(fig, width="stretch")

if tiene_real:
    dentro = ((df["real"] >= df["p10"]) & (df["real"] <= df["p90"])).mean()
    st.caption(f"Ese día, **{dentro:.0%}** de las horas reales cayeron dentro del rango del 80% (lo esperado es cerca de 80%).")

# ----- Tabla -----
with st.expander("Ver la tabla hora por hora", icon=":material/table:"):
    tabla = df[["hora", "p10", "p50", "p90", "hace_una_semana", "real"]].copy()
    tabla["hora"] = etiqueta_hora
    st.dataframe(
        tabla, hide_index=True, width="stretch",
        column_config={
            "hora": st.column_config.TextColumn("Hora"),
            "p10": st.column_config.NumberColumn("Mínimo probable (p10)", format="%.0f"),
            "p50": st.column_config.ProgressColumn("Pronóstico (p50)", format="%.0f", min_value=0,
                                                   max_value=float(df["p90"].max())),
            "p90": st.column_config.NumberColumn("Máximo probable (p90)", format="%.0f"),
            "hace_una_semana": st.column_config.NumberColumn("Hace una semana", format="%.0f"),
            "real": st.column_config.NumberColumn("Real", format="%.0f"),
        },
    )

st.page_link("paginas/decision.py", label="¿Cuántos taxis enviar a esta zona? →", icon=":material/local_taxi:")
