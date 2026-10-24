"""Parte 4 · Ficha del modelo (model card) y comunicación ética. Todas las cifras salen del notebook."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from comun import AMARILLO, AQUA, AZUL, GRIS, NARANJA, dinero_delta, leer_csv, leer_json

met = leer_json("metricas_modelo.json")
errores_grupo = leer_csv("errores_por_grupo.csv")
errores_zona = leer_csv("errores_por_zona.csv")
errores_hora = leer_csv("errores_por_hora.csv")
importancia = leer_csv("importancia_variables.csv")

comp = pd.DataFrame(met["comparacion"]).set_index("Método")
mae_mod = comp.iloc[0]["MAE"]
mae_sem = comp.loc["Igual que hace una semana", "MAE"]
mae_ayer = comp.loc["Igual que ayer", "MAE"]
mejora = met["mejora_mae_vs_semana"]
cob = met["cobertura_80"]

st.title("Ficha del modelo")
st.caption("Una ficha del modelo (*model card*) explica en una página para qué sirve un modelo, qué tan bien funciona "
           "y para qué **no** debe usarse. Todas las cifras salen del notebook `preparacion.ipynb`.")

# ----- 1. Para qué sirve -----
with st.container(border=True):
    st.subheader(":material/target: Para qué sirve")
    st.markdown(
        f"Pronostica **cuántos viajes de taxi amarillo empezarán en cada zona y cada hora del día siguiente**, "
        f"con un rango de incertidumbre (cuantiles del 10% al 90%). Sirve para **planificar cuántos taxis enviar** "
        f"a las {met['zonas_pronosticadas']} zonas con más demanda de Nueva York, que concentran el "
        f"{met['pct_viajes_cubiertos']:.0%} de los viajes."
    )
    a, b, c = st.columns(3)
    a.markdown(f"**Modelo**  \n{met['modelo']}, {met['parametros']['n_estimators']} árboles de profundidad "
               f"{met['parametros']['max_depth']} (elegidos por validación en el tiempo)")
    b.markdown(f"**Datos**  \nViajes de taxi amarillo NYC TLC, enero 2024. Entrenamiento: {met['entrenamiento']} "
               f"({met['filas_entrenamiento']:,} horas-zona)")
    c.markdown(f"**Evaluación**  \nPor tiempo, nunca al azar: semana del {met['prueba']} "
               f"({met['filas_prueba']:,} horas-zona que el modelo no vio)")
    st.markdown("**Variables:** viajes de la misma hora ayer, anteayer y hace una semana (±1 h), promedio del día anterior, "
                "hora, día de la semana, fin de semana, feriado y la zona. Ningún dato de menos de 24 horas: el pronóstico se "
                "hace el día anterior.")

# ----- 2. Qué tan bien funciona -----
st.subheader(":material/speed: Qué tan bien funciona")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Error medio del modelo (MAE)", f"{mae_mod:.1f} viajes/h", border=True,
          delta=f"{-mejora:+.1%} vs hace una semana", delta_color="inverse")
k2.metric("Regla 'igual que hace una semana'", f"{mae_sem:.1f} viajes/h", border=True)
k3.metric("Regla 'igual que ayer'", f"{mae_ayer:.1f} viajes/h", border=True)
k4.metric("Cobertura real del rango 80%", f"{cob:.1%}", delta=f"{cob - 0.8:+.1%} vs 80% ideal", delta_color="off", border=True)

if mejora >= 0.15:
    veredicto = f"El modelo **le gana claramente** a la regla simple: reduce el error medio un {mejora:.0%}."
elif mejora > 0:
    veredicto = (f"El modelo **le gana por poco** a la regla simple (reduce el error un {mejora:.0%}). La demanda de taxis "
                 "se repite mucho de una semana a otra. **Su valor principal está en el rango de incertidumbre**, que la regla "
                 "simple no da y que permite decidir cuántos taxis enviar según los costos.")
else:
    veredicto = ("El modelo **no le gana** a 'igual que hace una semana' en la mediana. Su aporte es el rango de "
                 "incertidumbre, que permite decidir según los costos.")
st.markdown(veredicto)

c1, c2 = st.columns([3, 2])
with c1:
    tabla = comp.reset_index()
    st.dataframe(tabla, hide_index=True, width="stretch",
                 column_config={"MAE": st.column_config.NumberColumn("MAE (viajes/h)", format="%.2f"),
                                "WAPE": st.column_config.ProgressColumn("WAPE (error / viajes)", format="percent",
                                                                       min_value=0, max_value=float(comp["WAPE"].max()) * 1.1)})
    st.caption(f"**Pinball loss** promedio de los 9 cuantiles: {met['pinball']:.2f}. "
               "WAPE = suma de errores absolutos / suma de viajes reales.")
    cobertura_txt = ("cubre casi exactamente lo prometido" if abs(cob - 0.8) <= 0.03 else
                     "cubre **menos** de lo prometido: el rango es algo estrecho, hay más sorpresas de las que el modelo cree"
                     if cob < 0.8 else "cubre **más** de lo prometido: el rango es algo ancho (conservador)")
    st.markdown(f"**¿El rango del 80% cubre el 80%?** En la semana de prueba cubrió el **{cob:.1%}** de las horas: {cobertura_txt}.")
with c2:
    cal = pd.DataFrame(met["calibracion"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=GRIS, dash="dot", width=2), name="Ideal"))
    fig.add_trace(go.Scatter(x=cal["cuantil"], y=cal["fraccion_real_debajo"], mode="lines+markers", name="Modelo",
                             line=dict(color=AZUL, width=2), marker=dict(size=8),
                             hovertemplate="Cuantil %{x:.0%}: %{y:.1%} de los reales debajo<extra></extra>"))
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10), title="Calibración de los cuantiles",
                      xaxis=dict(title="Cuantil pedido", tickformat=".0%"), yaxis=dict(title="Reales por debajo", tickformat=".0%"),
                      legend=dict(orientation="h", y=-0.3), plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")

# ----- 3. Dónde se equivoca más -----
st.subheader(":material/troubleshoot: Dónde se equivoca más")
peor = errores_grupo.sort_values("WAPE_modelo", ascending=False).iloc[0]
mejor = errores_grupo.sort_values("WAPE_modelo").iloc[0]
st.markdown(f"Por **tipo de zona** (une el pronóstico con la segmentación): el error relativo es mayor en "
            f"**{peor['grupo']}** (WAPE {peor['WAPE_modelo']:.0%}, cobertura {peor['cobertura_80']:.0%}) y menor en "
            f"**{mejor['grupo']}** (WAPE {mejor['WAPE_modelo']:.0%}).")
g1, g2 = st.columns(2)
with g1:
    eg = errores_grupo.sort_values("WAPE_modelo")
    fig_g = go.Figure()
    fig_g.add_trace(go.Bar(y=eg["grupo"], x=eg["WAPE_modelo"], orientation="h", name="Modelo",
                           marker=dict(color=AZUL, cornerradius=4), hovertemplate="Modelo: %{x:.1%}<extra></extra>"))
    fig_g.add_trace(go.Bar(y=eg["grupo"], x=eg["WAPE_semana"], orientation="h", name="Hace una semana",
                           marker=dict(color=GRIS, cornerradius=4), hovertemplate="Hace una semana: %{x:.1%}<extra></extra>"))
    fig_g.update_layout(height=300, barmode="group", margin=dict(l=10, r=10, t=30, b=10), title="WAPE por tipo de zona",
                        xaxis=dict(tickformat=".0%"), legend=dict(orientation="h", y=-0.2), plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_g, width="stretch")
with g2:
    fig_h = go.Figure()
    fig_h.add_trace(go.Scatter(x=errores_hora["hora_dia"], y=errores_hora["MAE_modelo"], mode="lines+markers", name="Modelo",
                               line=dict(color=AZUL, width=2)))
    fig_h.add_trace(go.Scatter(x=errores_hora["hora_dia"], y=errores_hora["MAE_semana"], mode="lines", name="Hace una semana",
                               line=dict(color=GRIS, width=2, dash="dot")))
    fig_h.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10), title="Error medio por hora del día",
                        xaxis_title="Hora", yaxis_title="MAE (viajes/h)", hovermode="x unified",
                        legend=dict(orientation="h", y=-0.3), plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_h, width="stretch")

with st.expander("Zonas con mayor error relativo", icon=":material/list:"):
    st.dataframe(errores_zona.head(15)[["nombre", "distrito", "grupo", "viajes_hora", "WAPE_modelo", "WAPE_semana", "cobertura_80"]],
                 hide_index=True, width="stretch",
                 column_config={"nombre": "Zona", "distrito": "Distrito", "grupo": "Tipo de zona",
                                "viajes_hora": st.column_config.NumberColumn("Viajes/h", format="%.1f"),
                                "WAPE_modelo": st.column_config.NumberColumn("WAPE modelo", format="percent"),
                                "WAPE_semana": st.column_config.NumberColumn("WAPE hace una semana", format="percent"),
                                "cobertura_80": st.column_config.NumberColumn("Cobertura 80%", format="percent")})

# ----- 4. Importancia de variables -----
st.subheader(":material/bar_chart: Importancia de variables: en qué se apoya el modelo")
NOMBRES_VAR = {
    "lag_168": "Misma hora, hace una semana", "lag_167": "Hora siguiente, hace una semana",
    "lag_169": "Hora anterior, hace una semana", "lag_24": "Misma hora, ayer", "lag_48": "Misma hora, anteayer",
    "media_dia_ant": "Promedio por hora de ayer", "hora_dia": "Hora del día", "dia_semana": "Día de la semana",
    "fin_semana": "Fin de semana", "feriado": "Feriado", "zona": "Zona",
}
FAMILIA = {"lag_168": "Hace una semana", "lag_167": "Hace una semana", "lag_169": "Hace una semana",
           "lag_24": "Ayer y anteayer", "lag_48": "Ayer y anteayer", "media_dia_ant": "Ayer y anteayer",
           "hora_dia": "Calendario", "dia_semana": "Calendario", "fin_semana": "Calendario", "feriado": "Calendario",
           "zona": "Zona"}
COLOR_FAMILIA = {"Hace una semana": AZUL, "Ayer y anteayer": NARANJA, "Calendario": AQUA, "Zona": AMARILLO}

imp = importancia.assign(nombre=importancia["variable"].map(NOMBRES_VAR).fillna(importancia["variable"]),
                         familia=importancia["variable"].map(FAMILIA).fillna("Zona"))
por_familia = imp.groupby("familia")["porcentaje"].sum()

vista_imp = st.segmented_control("Ver la importancia", ["Por variable", "Por tipo de variable"],
                                 default="Por variable", key="vista_importancia") or "Por variable"
if vista_imp == "Por variable":
    d = imp.sort_values("porcentaje")
    etiquetas = d["nombre"] + " (" + d["variable"] + ")"
    colores = d["familia"].map(COLOR_FAMILIA)
else:
    d = por_familia.sort_values().rename("porcentaje").reset_index()
    etiquetas = d["familia"]
    colores = d["familia"].map(COLOR_FAMILIA)
fig_i = go.Figure(go.Bar(y=etiquetas, x=d["porcentaje"], orientation="h", marker=dict(color=list(colores), cornerradius=4),
                         hovertemplate="%{y}: %{x:.1%}<extra></extra>", text=[f"{v:.0%}" for v in d["porcentaje"]],
                         textposition="outside"))
fig_i.update_layout(height=360 if vista_imp == "Por variable" else 240, margin=dict(l=10, r=40, t=10, b=10),
                    xaxis=dict(tickformat=".0%", title="Importancia (ganancia, % del total)"), plot_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig_i, width="stretch")
st.caption("Colores por tipo de variable: " + " · ".join(
    f"<span style='color:{c}'>■</span> {f}" for f, c in COLOR_FAMILIA.items()), unsafe_allow_html=True)

top = imp.sort_values("porcentaje", ascending=False).iloc[0]
st.markdown(
    f"**Lectura.** El modelo se apoya sobre todo en **{top['nombre'].lower()}** ({top['porcentaje']:.0%} de la ganancia). "
    f"Sumando por tipo: lo que pasó **hace una semana** pesa {por_familia.get('Hace una semana', 0):.0%}, lo de **ayer y anteayer** "
    f"{por_familia.get('Ayer y anteayer', 0):.0%}, el **calendario** {por_familia.get('Calendario', 0):.0%} y la **zona** "
    f"{por_familia.get('Zona', 0):.0%}. Por eso el modelo casi empata con la regla \"igual que hace una semana\": usa ese mismo "
    "dato como base y lo corrige con lo que pasó ayer y con el día y la hora. La zona pesa poco porque los valores pasados ya "
    "dicen cuánta demanda tiene cada zona."
)
with st.expander("Ver la tabla de importancia", icon=":material/table:"):
    st.dataframe(imp.sort_values("porcentaje", ascending=False)[["nombre", "variable", "familia", "porcentaje"]],
                 hide_index=True, width="stretch",
                 column_config={"nombre": "Variable", "variable": "Nombre en el código", "familia": "Tipo",
                                "porcentaje": st.column_config.ProgressColumn("Importancia (ganancia)", format="percent",
                                                                              min_value=0, max_value=1)})
st.caption("La importancia por ganancia (*gain*) mide cuánto mejora el modelo, en promedio, cada vez que usa esa variable. "
           "Muestra en qué se apoya el pronóstico, no que una variable *cause* la demanda. Sale de `preparacion.ipynb` "
           "(archivo `app/data/importancia_variables.csv`).")

# ----- 5. Decisión y costos -----
ce = met["costos_ejemplo"]
tot = ce["totales"]
nombres = list(tot)
st.subheader(":material/payments: Valor para la decisión")
st.markdown(f"Con un taxi ocioso a **US\\${ce['costo_ocioso']}** y un pasajero perdido a **US\\${ce['costo_perdido']}** "
            f"(cuantil óptimo {ce['cuantil']:.2f}), en toda la semana de prueba y todas las zonas:")
d1, d2, d3 = st.columns(3)
d1.metric(nombres[0], f"${tot[nombres[0]]:,.0f}", border=True)
d2.metric(nombres[1], f"${tot[nombres[1]]:,.0f}", delta=f"{dinero_delta(tot[nombres[1]] - tot[nombres[0]])} vs cuantil óptimo", delta_color="inverse", border=True)
d3.metric(nombres[2], f"${tot[nombres[2]]:,.0f}", delta=f"{dinero_delta(tot[nombres[2]] - tot[nombres[0]])} vs cuantil óptimo", delta_color="inverse", border=True)

# ----- 6. Limitaciones y usos no recomendados -----
st.subheader(":material/warning: Limitaciones")
st.markdown(
    """
- **Un solo mes de datos (enero 2024).** No conoce estacionalidad anual, verano, fiestas de fin de año ni otros feriados.
- **No ve el clima, eventos, vuelos ni cierres de calles.** Una tormenta de nieve, un concierto o retrasos en el aeropuerto
  cambian la demanda y el modelo no lo sabe.
- **Cuenta viajes, no demanda.** Si alguien no encontró taxi, ese viaje no aparece en los datos: en horas con pocos taxis
  disponibles el modelo subestima la demanda real.
- **Solo taxis amarillos.** No incluye Uber, Lyft ni taxis verdes, que dominan en muchos barrios fuera de Manhattan.
- **Solo zonas con ≥ 3,000 viajes al mes.** Las demás no tienen pronóstico.
- **Supone que un taxi atiende un viaje por hora** al recomendar cuántos enviar.
    """
)
st.subheader(":material/block: Usos no recomendados y a quién podría perjudicar")
st.markdown(
    """
- **No usarlo para recortar servicio en barrios con poca demanda de taxi amarillo.** Que haya pocos viajes puede reflejar que
  *ya* hay pocos taxis ahí (la demanda insatisfecha no se registra), no que la gente no los necesite. Recortar con base en este
  modelo reforzaría el problema y perjudicaría sobre todo a **residentes de los distritos exteriores (Bronx, Queens, Brooklyn,
  Staten Island), personas mayores o con movilidad reducida** que dependen del taxi.
- **No usarlo para fijar tarifas dinámicas** ni para evaluar el desempeño individual de conductores.
- **No usarlo en días atípicos** (tormentas, huelgas, grandes eventos) sin revisión humana: ahí el rango del 80% deja de ser confiable.
- **No usarlo sin reentrenar** en otros meses o años: los patrones cambian.
- **Las zonas sin pronóstico quedan fuera** de la planificación: la gerente debe decidir con otra regla para ellas, no ignorarlas.

La recomendación es un **apoyo**: la decisión final la toma una persona que conoce el contexto del día.
    """
)

# ----- Síntesis Conceptual (Módulo 4 · Semana 10) -----
with st.expander(":material/account_tree: Síntesis conceptual · Interpretabilidad, Evaluación y Estructura (Semana 10)"):
    st.markdown(
        """
**1. Mapa conceptual jerárquico del sistema**
- **Estructura del proyecto (inspirada en Cookiecutter Data Science):** separación reproducible entre exploración y entrenamiento (`preparacion.ipynb`), datos procesados (`app/data/`), servicio de inferencia desacoplado (`api/`) e interfaz de decisión (`app/`).
- **Interpretabilidad del modelo (3 niveles complementarios):**
  - *Coeficientes lineales:* miden el efecto marginal directo con signo ($+$ o $-$) asumiendo linealidad, pero no capturan interacciones complejas entre hora y zona.
  - *Importancia de variables por ganancia (Gain en árboles):* cuantifica qué porcentaje de la reducción de error aporta cada variable a nivel **global** (en este modelo: `lag_168` 58.2%, `lag_24` 24.8%, `lag_169` 4.4%, `lag_167` 3.7%), aunque sin indicar la dirección del efecto en un caso individual.
  - *Valores SHAP (Shapley Additive exPlanations):* descomponen cada predicción **local** como la suma del valor base más el aporte con signo de cada variable, unificando explicabilidad local y global.
- **De la predicción a la decisión responsable:** regresión cuantílica (`p10`–`p90`) $\\rightarrow$ optimización por razón crítica $q^* = C_p / (C_p + C_o)$ $\\rightarrow$ monitoreo diario de degradación (WAPE) y auditoría ética contra sesgos de demanda censurada en distritos exteriores.

| Método | Nivel | ¿Da signo ($+$ / $-$)? | Aplicación en Taxis NYC |
| :--- | :--- | :--- | :--- |
| **Coeficientes lineales** | Global | Sí | Útil como referencia simple, insuficiente para picos horarios no lineales |
| **Importancia por ganancia (Gain)** | Global | No (magnitud $\\ge 0$) | Muestra que la memoria semanal (`lag_168` ± 1 h = 66.3%) y del día anterior (`lag_24` = 24.8%) dominan el pronóstico |
| **Valores SHAP** | Local y Global | Sí | Explica por qué en una zona y hora específica el pronóstico sube o baja respecto al promedio |
        """
    )

# ----- Opinión del usuario -----
st.divider()
st.markdown("**¿Te fue útil esta ficha para decidir cuánto confiar en el modelo?**")
calificacion = st.feedback("stars", key="feedback_ficha")
if calificacion is not None and st.session_state.get("feedback_enviado") != calificacion:
    st.session_state["feedback_enviado"] = calificacion
    st.toast(f"¡Gracias! Registramos {calificacion + 1} de 5 estrellas.", icon=":material/thumb_up:")
