"""Taxis NYC · app para quien toma decisiones (punto de entrada).

Correr local:  streamlit run app/streamlit_app.py
"""
import streamlit as st

from comun import api_url

st.set_page_config(page_title="Taxis NYC · Planificador", page_icon=":material/local_taxi:", layout="wide")

paginas = {
    "Planificar": [
        st.Page("paginas/pronostico.py", title="Pronóstico", icon=":material/insights:", default=True),
        st.Page("paginas/decision.py", title="Cuántos taxis enviar", icon=":material/local_taxi:", url_path="decision"),
    ],
    "Entender": [
        st.Page("paginas/segmentacion.py", title="Tipos de zona", icon=":material/scatter_plot:", url_path="segmentacion"),
        st.Page("paginas/ficha.py", title="Ficha del modelo", icon=":material/fact_check:", url_path="ficha"),
    ],
    "Vigilar": [
        st.Page("paginas/monitoreo.py", title="Monitoreo", icon=":material/monitor_heart:", url_path="monitoreo"),
    ],
}
pg = st.navigation(paginas)

with st.sidebar:
    st.markdown("### :material/local_taxi: Taxis NYC")
    st.caption("Pronóstico de viajes, tipos de zona y plan de taxis por hora · enero 2024")
    estado_api = st.empty()
    with st.popover("Acerca de", icon=":material/info:", width="stretch"):
        st.markdown(
            "Proyecto AIMLF1 · Módulo 2 · **Oscar Orantes**\n\n"
            "- La **app** (Streamlit) nunca carga el modelo: se lo pide a la **API** (FastAPI en Render).\n"
            "- Los tipos de zona y las cifras de la ficha salen del notebook `preparacion.ipynb`.\n\n"
            f"Documentación de la API: [{api_url()}/docs]({api_url()}/docs)"
        )

pg.run()

# Indicador del estado de la API (según la última llamada de esta sesión)
estado = st.session_state.get("api_estado")
with estado_api.container():
    if estado == "ok":
        st.badge("API en línea", icon=":material/cloud_done:", color="green")
    elif estado == "caida":
        st.badge("API sin respuesta", icon=":material/cloud_off:", color="red")
    else:
        st.badge("API sin consultar", icon=":material/cloud:", color="gray")
