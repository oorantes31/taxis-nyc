# Taxis NYC: Análisis + visualización de importancia de variables

**AIMLF1 · Módulo 2** · Una app para quien toma decisiones. Pronóstico con incertidumbre, segmentación de zonas y una recomendación de cuántos
taxis enviar, en una app de Streamlit que consulta su propia API.

| | Link |
|---|---|
| App (Streamlit Community Cloud) | `https://PEGAR-LINK-DE-LA-APP.streamlit.app` |
| API (Render) · documentación | `https://PEGAR-LINK-DE-LA-API.onrender.com/docs` |
| Repositorio | `https://github.com/oorantes31/taxis-nyc` |

## Integrantes

- Oscar Orantes (entrega individual)

> La API gratuita de Render se duerme tras 15 minutos sin uso: la primera consulta puede tardar cerca de un minuto.
> Mientras tanto la app lo indica y las páginas *Tipos de zona* y *Ficha del modelo* siguen funcionando.

## Qué hace la app

| Página | Parte | Qué muestra |
|---|---|---|
| Pronóstico | 1 | Viajes por hora de una zona y fecha (25 ene – 1 feb 2024) con banda p10–p90, mediana, valores reales y "hace una semana". Pide los datos a la API. |
| Cuántos taxis enviar | 3 | El usuario fija el costo de un taxi ocioso y de un pasajero perdido; la app calcula el cuantil óptimo `Cp / (Cp + Co)`, recomienda taxis por hora, compara costos contra p50 y "hace una semana" y permite descargar el plan (CSV). |
| Tipos de zona | 2 | K-Means (k elegido con silueta) sobre 8 variables escaladas, PCA en 2D, grupos nombrados por su perfil, mapa de calor de las variables que distinguen a cada grupo, selección de zonas en el gráfico y tabla con perfil horario. |
| Ficha del modelo | 4 | Para qué sirve, datos, evaluación por tiempo, métricas frente a reglas simples, cobertura del rango 80%, errores por tipo de zona y hora, **importancia de variables** (por variable y por tipo, con su lectura), limitaciones y usos no recomendados. |
| Monitoreo (extra) | +10 | Error (WAPE) día a día de la semana de prueba por ciudad, tipo de zona o zona, con alerta cuando pasa un límite configurable. |

**Funciones avanzadas de Streamlit usadas:** `st.navigation` + `st.Page` (secciones e íconos), `@st.fragment`, `@st.dialog`,
`st.plotly_chart(on_select="rerun")`, `st.column_config` (ProgressColumn, LineChartColumn), `@st.cache_data`, `st.secrets`,
`st.query_params` + `st.session_state`, `st.status`, `st.toast`, `st.pills`, `st.segmented_control`, `st.badge`, `st.popover`,
`st.metric(chart_data=..., border=True)`, `st.feedback`, `st.download_button`, `st.switch_page` y tema propio en `.streamlit/config.toml`.

## Resultados principales (semana de prueba 25–31 ene 2024, 58 zonas)

| Método | MAE (viajes/h) | WAPE |
|---|---|---|
| Modelo XGBoost de cuantiles (p50) | 11.77 | 16.6% |
| Igual que hace una semana | 11.88 | 16.8% |
| Igual que ayer | 21.29 | 30.1% |

- El modelo le gana **por poco** a "igual que hace una semana" en la mediana; la demanda se repite mucho semana a semana.
- Su valor está en el **rango de incertidumbre**: el rango p10–p90 cubrió el 87.6% de las horas (algo conservador).
- Con costos de US$10 (taxi ocioso) y US$40 (pasajero perdido), enviar el cuantil p80 habría costado **US$2.23 M** en la semana,
  contra US$3.16 M de enviar la mediana o lo de hace una semana (≈ 30% menos).

- **Importancia de variables:** "misma hora hace una semana" (`lag_168`) aporta el 58% de la ganancia y "misma hora ayer" (`lag_24`) el 25%:
  el modelo parte de lo de hace una semana y lo corrige con lo de ayer, por eso casi empata con esa regla.

Todas las cifras salen de `preparacion.ipynb`.

## Estructura

```
taxis-nyc/
├── preparacion.ipynb          # datos, modelos y métricas (ejecutado)
├── api/
│   ├── main.py                # FastAPI: GET /, /info, /pronostico
│   ├── modelo_pronostico.ubj  # XGBoost reg:quantileerror (9 cuantiles, objetivo en log1p)
│   ├── demanda.parquet        # filas del 25 ene al 1 feb con sus variables ya calculadas
│   ├── meta_modelo.json       # variables, categorías de zona, cuantiles
│   └── requirements.txt
├── app/
│   ├── streamlit_app.py       # punto de entrada (st.navigation)
│   ├── comun.py               # conexión con la API, datos y selectores compartidos
│   ├── paginas/               # pronostico, decision, segmentacion, ficha, monitoreo
│   ├── data/                  # zonas segmentadas y métricas (salen del notebook)
│   ├── .streamlit/config.toml # tema de colores
│   └── requirements.txt
└── README.md
```

## Contrato de la API

| Endpoint | Recibe | Devuelve |
|---|---|---|
| `GET /` | — | Que la API está en línea |
| `GET /info` | — | Zonas pronosticables (id, nombre, distrito), fechas disponibles y con datos reales, cuantiles |
| `GET /pronostico` | `zona_id`, `fecha` (AAAA-MM-DD) | 24 horas con `cuantiles` p10…p90, `real` (o `null`) y `hace_una_semana` |

Una zona o fecha que no existe responde **404** con un mensaje claro. Ejemplo: `/pronostico?zona_id=161&fecha=2024-01-25`.

## Cómo correr el proyecto

**1. Notebook** (opcional; los archivos que genera ya están en el repositorio). En Colab o local, desde la raíz del repo:
abre `preparacion.ipynb` y ejecuta todo. Si no encuentra los datos en `datos/`, los descarga de la NYC TLC.
Genera `api/modelo_pronostico.ubj`, `api/demanda.parquet`, `api/meta_modelo.json` y los archivos de `app/data/`.

**2. API**

```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload        # http://localhost:8000/docs
```

**3. App** (en otra terminal)

```bash
cd app
pip install -r requirements.txt
# Opcional: crear app/.streamlit/secrets.toml con API_URL = "http://localhost:8000"
streamlit run streamlit_app.py
```

Sin `secrets.toml` la app usa `http://localhost:8000` (o la variable de entorno `API_URL`).

## Publicación

- **Render** (API): New → Web Service → este repositorio · Root Directory `api` · Build `pip install -r requirements.txt` ·
  Start `uvicorn main:app --host 0.0.0.0 --port $PORT` · Instance Free.
- **Streamlit Community Cloud** (app): Create app → este repositorio · Main file `app/streamlit_app.py` ·
  Advanced settings → Secrets: `API_URL = "https://su-api.onrender.com"` (sin `/` al final).

## Datos

Viajes de taxi amarillo de enero 2024 y tabla de zonas de la
[NYC Taxi & Limousine Commission](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page).
