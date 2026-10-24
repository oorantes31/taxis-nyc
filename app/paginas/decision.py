"""Parte 3 · Decisión: cuántos taxis enviar por hora según el costo de equivocarse."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from comun import (AZUL, NARANJA, ErrorAPI, cargar_info, dinero_delta, fecha_corta, mostrar_error_api, pronostico,
                   selector_zona_fecha)

CUANTILES = np.round(np.arange(0.1, 1.0, 0.1), 1)


def costo_horas(enviados, real, c_ocioso, c_perdido):
    enviados, real = np.asarray(enviados, float), np.asarray(real, float)
    return np.maximum(enviados - real, 0) * c_ocioso + np.maximum(real - enviados, 0) * c_perdido


def cuantil_cercano(q):
    """La API entrega p10…p90: usamos el disponible más cercano al óptimo."""
    return float(CUANTILES[np.abs(CUANTILES - q).argmin()])


st.title("¿Cuántos taxis enviar?")
st.markdown("Si quedarse corto cuesta más que pasarse, conviene enviar **más** que el pronóstico central, y al revés. "
            "Fija los dos costos y la app calcula cuántos taxis enviar en cada hora.")

info = cargar_info()
zona_id, fecha = selector_zona_fecha(info, clave="dec")

try:
    with st.spinner("Pidiendo el pronóstico a la API…"):
        df = pronostico(zona_id, fecha)
except ErrorAPI as e:
    mostrar_error_api(e)

zona = df.attrs["zona"]
tiene_real = bool(df.attrs["tiene_real"])


@st.fragment
def panel_decision(df: pd.DataFrame):
    """Mover los costos solo recalcula esta parte de la página (no vuelve a llamar a la API)."""
    c1, c2 = st.columns(2)
    c_ocioso = c1.number_input("Costo de un taxi una hora sin pasajero (US$)", min_value=1, max_value=500, value=10, step=1)
    c_perdido = c2.number_input("Costo de un pasajero que no encuentra taxi (US$)", min_value=1, max_value=500, value=40, step=1)
    q_opt = c_perdido / (c_perdido + c_ocioso)
    q_usado = cuantil_cercano(q_opt)
    col_q = f"p{int(round(q_usado * 100))}"
    with st.container(border=True):
        f1, f2 = st.columns([3, 2], vertical_alignment="center")
        f1.latex(r"q^{*} = \frac{C_{perdido}}{C_{perdido} + C_{ocioso}} = \frac{%d}{%d + %d} = %.2f" % (c_perdido, c_perdido, c_ocioso, q_opt))
        f2.markdown(f"**Cuantil óptimo: {q_opt:.0%}**  \nSe usa el cuantil disponible más cercano que entrega la API: **{col_q}**")

    if q_opt > 0.5:
        explicacion = (f"Perder un pasajero (US\\${c_perdido}) cuesta **más** que tener un taxi ocioso (US\\${c_ocioso}). "
                       f"Por eso conviene enviar de más: la cantidad que la demanda **no supera el {q_usado:.0%} de las veces**.")
    elif q_opt < 0.5:
        explicacion = (f"Un taxi ocioso (US\\${c_ocioso}) cuesta **más** que perder un pasajero (US\\${c_perdido}). "
                       f"Por eso conviene enviar de menos: una cantidad que la demanda supera el {1 - q_usado:.0%} de las veces.")
    else:
        explicacion = "Los dos errores cuestan lo mismo: se envía el pronóstico central (la mediana)."
    if not (0.1 <= q_opt <= 0.9):
        explicacion += f" El óptimo exacto ({q_opt:.2f}) está fuera de los cuantiles que entrega el modelo; se usa el más cercano."
    st.info(explicacion, icon=":material/lightbulb:")

    plan = pd.DataFrame({"hora": df["hora"], "taxis_recomendados": np.ceil(df[col_q]).astype(int),
                         "pronostico_central_p50": np.round(df["p50"]).astype(int),
                         "rango_p10": np.round(df["p10"]).astype(int), "rango_p90": np.round(df["p90"]).astype(int)})

    # Gráfico: taxis recomendados por hora vs pronóstico central y real
    etiquetas = [f"{h:02d}:00" for h in plan["hora"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=etiquetas, y=plan["taxis_recomendados"], name=f"Taxis a enviar ({col_q})",
                         marker=dict(color=AZUL, cornerradius=4), hovertemplate="Enviar: %{y}<extra></extra>"))
    fig.add_trace(go.Scatter(x=etiquetas, y=df["p50"], mode="lines", name="Pronóstico central (p50)",
                             line=dict(color=NARANJA, width=2), hovertemplate="p50: %{y:.0f}<extra></extra>"))
    if tiene_real:
        fig.add_trace(go.Scatter(x=etiquetas, y=df["real"], mode="markers", name="Viajes reales",
                                 marker=dict(color="#0b0b0b", size=8, line=dict(color="white", width=2)),
                                 hovertemplate="Real: %{y:.0f}<extra></extra>"))
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10), hovermode="x unified", bargap=0.25,
                      legend=dict(orientation="h", y=1.1, x=0), yaxis_title="Taxis / viajes", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_yaxes(gridcolor="rgba(0,0,0,0.08)")
    st.plotly_chart(fig, width="stretch")

    st.markdown(f"**Plan:** enviar en total **{plan['taxis_recomendados'].sum():,} taxis-hora** a {zona['nombre']} "
                f"el {fecha_corta(fecha)} (el pronóstico central sumaría {plan['pronostico_central_p50'].sum():,}).")

    # Comparación de costos con días reales
    if tiene_real:
        real = df["real"].values
        costo_rec = costo_horas(plan["taxis_recomendados"], real, c_ocioso, c_perdido).sum()
        costo_p50 = costo_horas(plan["pronostico_central_p50"], real, c_ocioso, c_perdido).sum()
        costo_sem = costo_horas(df["hace_una_semana"], real, c_ocioso, c_perdido).sum()
        st.subheader("¿Cuánto habría costado ese día?")
        k1, k2, k3 = st.columns(3)
        k1.metric("Nuestra recomendación", f"${costo_rec:,.0f}", border=True)
        k2.metric("Enviar el pronóstico central (p50)", f"${costo_p50:,.0f}", delta=f"{dinero_delta(costo_p50 - costo_rec)} vs recomendación",
                  delta_color="inverse", border=True)
        k3.metric("Enviar lo de hace una semana", f"${costo_sem:,.0f}", delta=f"{dinero_delta(costo_sem - costo_rec)} vs recomendación",
                  delta_color="inverse", border=True)
        st.caption("Costo de cada hora = taxis de más × costo ocioso + pasajeros sin taxi × costo perdido. "
                   "Suponemos que un taxi atiende un viaje por hora.")
    else:
        st.info("Este día es mañana: el costo se podrá medir cuando existan los viajes reales. "
                "Abajo puedes ver cómo le habría ido a la regla en la semana de prueba.", icon=":material/event_upcoming:")

    # Toda la semana de prueba (7 llamadas a la API, guardadas en caché)
    with st.expander("Comparar en toda la semana de prueba (25–31 ene)", icon=":material/calendar_month:"):
        filas = []
        try:
            for f in info["fechas_con_real"]:
                d = pronostico(zona_id, f)
                r = d["real"].values
                filas.append({"fecha": fecha_corta(f),
                              "Recomendación": costo_horas(np.ceil(d[col_q]), r, c_ocioso, c_perdido).sum(),
                              "Pronóstico central": costo_horas(np.round(d["p50"]), r, c_ocioso, c_perdido).sum(),
                              "Hace una semana": costo_horas(d["hace_una_semana"], r, c_ocioso, c_perdido).sum()})
        except ErrorAPI as e:
            st.warning(f"No se pudo completar la semana: {e}")
        if filas:
            semana = pd.DataFrame(filas)
            totales = semana[["Recomendación", "Pronóstico central", "Hace una semana"]].sum()
            st.dataframe(semana, hide_index=True, width="stretch",
                         column_config={c: st.column_config.NumberColumn(c, format="dollar") for c in totales.index})
            mejor = totales.idxmin()
            st.markdown(f"En la semana, la regla más barata fue **{mejor}** (US\\${totales.min():,.0f}). "
                        f"La recomendación ahorró **US\\${totales['Pronóstico central'] - totales['Recomendación']:,.0f}** "
                        f"frente al pronóstico central y **US\\${totales['Hace una semana'] - totales['Recomendación']:,.0f}** "
                        "frente a enviar lo de hace una semana.")

    st.download_button("Descargar el plan de taxis por hora (CSV)", plan.to_csv(index=False).encode("utf-8"),
                       file_name=f"plan_taxis_zona{zona_id}_{fecha}.csv", mime="text/csv",
                       icon=":material/download:", type="primary")


panel_decision(df)
