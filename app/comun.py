"""Funciones compartidas por todas las páginas: conexión con la API, datos locales y selección de zona/fecha."""
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

DATA = Path(__file__).parent / "data"

# Colores (paleta categórica validada para daltonismo; el orden es fijo, nunca se recicla)
AZUL, NARANJA, AQUA, AMARILLO, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
GRIS = "#8a8984"
PALETA = [AZUL, NARANJA, AQUA, AMARILLO, MAGENTA, "#008300", "#6250d6"]
SIMBOLOS = ["circle", "diamond", "square", "triangle-up", "x", "star", "cross"]
COLOR_BADGE = ["blue", "orange", "green", "yellow", "violet", "green", "violet"]

DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MESES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def api_url() -> str:
    """Dirección de la API: primero st.secrets (Streamlit Cloud), luego variable de entorno, luego local."""
    try:
        url = st.secrets["API_URL"]
    except Exception:
        url = os.environ.get("API_URL", "http://localhost:8000")
    return str(url).rstrip("/")


class ErrorAPI(Exception):
    def __init__(self, mensaje, sin_conexion=False):
        super().__init__(mensaje)
        self.sin_conexion = sin_conexion


@st.cache_data(ttl=3600, show_spinner=False)
def _get(url: str, params: tuple):
    respuesta = requests.get(url, params=dict(params), timeout=90)  # 90 s: Render puede estar despertando
    respuesta.raise_for_status()
    return respuesta.json()


def llamar_api(ruta: str, **params):
    """GET a la API con caché. Convierte cualquier falla en ErrorAPI con un mensaje claro."""
    try:
        datos = _get(api_url() + ruta, tuple(sorted(params.items())))
        st.session_state["api_estado"] = "ok"
        return datos
    except requests.HTTPError as e:
        try:
            detalle = e.response.json().get("detail", "")
        except Exception:
            detalle = ""
        st.session_state["api_estado"] = "ok"  # la API respondió, aunque sea con error
        raise ErrorAPI(detalle or f"La API respondió con error {e.response.status_code}.")
    except requests.RequestException:
        st.session_state["api_estado"] = "caida"
        raise ErrorAPI("No pudimos conectarnos con la API de pronóstico.", sin_conexion=True)


def mostrar_error_api(error: ErrorAPI):
    if error.sin_conexion:
        st.error(
            "**La API de pronóstico no responde.**\n\n"
            "El servicio gratuito de Render se duerme tras 15 minutos sin uso y tarda cerca de un minuto en despertar. "
            "Espera un momento y pulsa **Reintentar**. Las páginas *Tipos de zona* y *Ficha del modelo* "
            "siguen funcionando porque no dependen de la API.",
            icon=":material/cloud_off:",
        )
        st.caption(f"Dirección consultada: `{api_url()}`")
        st.sidebar.badge("API sin respuesta", icon=":material/cloud_off:", color="red")
    else:
        st.warning(f"**La API respondió con un aviso:** {error}", icon=":material/info:")
    if st.button("Reintentar", icon=":material/refresh:", type="primary"):
        _get.clear()
        st.rerun()
    st.stop()


def cargar_info():
    """/info con un indicador de avance la primera vez (la API puede estar dormida)."""
    try:
        if st.session_state.get("api_estado") != "ok":
            with st.status("Conectando con la API… si estaba dormida puede tardar cerca de un minuto.",
                           expanded=False) as estado:
                try:
                    info = llamar_api("/info")
                except ErrorAPI:
                    estado.update(label="La API no respondió", state="error")
                    raise
                estado.update(label="Conectado con la API", state="complete")
            return info
        return llamar_api("/info")
    except ErrorAPI as e:
        mostrar_error_api(e)


def pronostico(zona_id: int, fecha: str) -> pd.DataFrame:
    """Llama /pronostico y lo convierte en una tabla de 24 filas."""
    datos = llamar_api("/pronostico", zona_id=int(zona_id), fecha=fecha)
    filas = []
    for h in datos["horas"]:
        filas.append({"hora": h["hora"], "real": h["real"], "hace_una_semana": h["hace_una_semana"], **h["cuantiles"]})
    df = pd.DataFrame(filas)
    df.attrs["zona"] = datos["zona"]
    df.attrs["tiene_real"] = datos.get("tiene_real", df["real"].notna().any())
    return df


# ---------- Datos locales (precalculados en el notebook) ----------
@st.cache_data
def leer_csv(nombre: str) -> pd.DataFrame:
    return pd.read_csv(DATA / nombre)


@st.cache_data
def leer_json(nombre: str) -> dict:
    return json.loads((DATA / nombre).read_text(encoding="utf-8"))


@st.cache_data
def zonas_segmentadas() -> pd.DataFrame:
    df = leer_csv("zonas_segmentadas.csv")
    df["perfil_horario"] = df["perfil_horario"].apply(json.loads)
    return df


def orden_grupos() -> list:
    """Orden fijo de los grupos (para que el color siga al grupo, no a su posición en un filtro)."""
    return list(leer_json("meta_segmentacion.json")["grupos"].keys())


def color_grupo(grupo: str) -> str:
    grupos = orden_grupos()
    return PALETA[grupos.index(grupo) % len(PALETA)] if grupo in grupos else GRIS


def badge_grupo(grupo: str):
    grupos = orden_grupos()
    color = COLOR_BADGE[grupos.index(grupo) % len(COLOR_BADGE)] if grupo in grupos else "gray"
    st.badge(grupo, icon=":material/category:", color=color)


def grupo_de_zona(zona_id: int):
    df = zonas_segmentadas()
    fila = df[df["zona_id"] == zona_id]
    return None if fila.empty else fila["grupo"].iloc[0]


# ---------- Formatos ----------
def dinero_delta(valor: float) -> str:
    return f"{'+' if valor >= 0 else '-'}${abs(valor):,.0f}"


def fecha_corta(f: str) -> str:
    d = date.fromisoformat(f)
    return f"{DIAS[d.weekday()]} {d.day} {MESES[d.month]}"


def fecha_boton(f: str, fechas_con_real) -> str:
    return fecha_corta(f) + ("" if f in fechas_con_real else " · mañana")


# ---------- Zona y fecha compartidas entre páginas y en el link ----------
def selector_zona_fecha(info: dict, solo_con_real: bool = False, clave: str = ""):
    """Selector de zona (selectbox) y fecha (segmented control).

    Recuerda la elección entre páginas con st.session_state y la guarda en el link con st.query_params,
    así se puede compartir una URL que abre la misma zona y fecha.
    """
    zonas = {z["id"]: f"{z['nombre']} ({z['distrito']}) · #{z['id']}" for z in info["zonas"]}
    ids = list(zonas)
    fechas = info["fechas_con_real"] if solo_con_real else info["fechas"]

    qp = st.query_params
    if "zona_id" not in st.session_state:
        try:
            st.session_state["zona_id"] = int(qp.get("zona", 161))
        except ValueError:
            st.session_state["zona_id"] = 161
    if st.session_state["zona_id"] not in ids:
        st.session_state["zona_id"] = 161 if 161 in ids else ids[0]
    if "fecha" not in st.session_state:
        st.session_state["fecha"] = qp.get("fecha", fechas[0])
    if st.session_state["fecha"] not in fechas:
        st.session_state["fecha"] = fechas[0] if solo_con_real else fechas[-1]

    col_z, _ = st.columns([1, 1])
    with col_z:
        zona_id = st.selectbox("Zona", ids, index=ids.index(st.session_state["zona_id"]),
                               format_func=zonas.get, key=f"zona_{clave}")
    # La fecha va en su propia fila para que quepan los 8 botones
    fecha = st.segmented_control("Fecha", fechas, default=st.session_state["fecha"],
                                 format_func=lambda f: fecha_boton(f, info["fechas_con_real"]),
                                 key=f"fecha_{clave}")
    fecha = fecha or st.session_state["fecha"]  # si se deselecciona, se mantiene la anterior
    st.session_state["zona_id"], st.session_state["fecha"] = zona_id, fecha
    st.query_params.update({"zona": str(zona_id), "fecha": fecha})
    return zona_id, fecha
