"""API de pronóstico de viajes de taxi por zona y hora (Taxis NYC · AIMLF1).

Endpoints (contrato):
    GET /                 -> la API está en línea
    GET /info             -> zonas pronosticables, fechas disponibles y cuantiles
    GET /pronostico       -> 24 horas de una zona y fecha con sus cuantiles, el real y el de hace una semana

Correr local:  uvicorn main:app --reload   y abrir http://localhost:8000/docs
"""
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

AQUI = Path(__file__).parent
META = json.loads((AQUI / "meta_modelo.json").read_text(encoding="utf-8"))
VARIABLES = META["variables"]
CUANTILES = META["cuantiles"]          # ["p10", ..., "p90"]
CATEGORIAS_ZONA = META["categorias_zona"]

# Se carga una sola vez al iniciar
modelo = xgb.XGBRegressor()
modelo.load_model(AQUI / "modelo_pronostico.ubj")

demanda = pd.read_parquet(AQUI / "demanda.parquet")
demanda["hora"] = pd.to_datetime(demanda["hora"])
demanda["fecha"] = demanda["hora"].dt.date
# La zona debe ser categoría con las MISMAS categorías del entrenamiento
demanda["zona"] = pd.Categorical(demanda["PULocationID"], categories=CATEGORIAS_ZONA)

ZONAS = (demanda[["PULocationID", "zona_nombre", "distrito"]].drop_duplicates()
         .sort_values("PULocationID"))
FECHAS = sorted(demanda["fecha"].unique())
FECHAS_CON_REAL = sorted(demanda.loc[demanda["viajes"].notna(), "fecha"].unique())


def _num(valor):
    """Convierte NaN a None para que el JSON tenga null."""
    return None if pd.isna(valor) else float(valor)


app = FastAPI(
    title="API Taxis NYC",
    description="Pronóstico de viajes por hora con incertidumbre (cuantiles p10–p90) para zonas de taxi amarillo de NYC.",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


@app.get("/", summary="Estado de la API")
def raiz():
    return {"estado": "en línea", "mensaje": "API Taxis NYC. Documentación en /docs",
            "endpoints": ["/info", "/pronostico?zona_id=161&fecha=2024-01-25"]}


@app.get("/info", summary="Zonas, fechas y cuantiles disponibles")
def info():
    return {
        "zonas": [{"id": int(z.PULocationID), "nombre": z.zona_nombre, "distrito": z.distrito}
                  for z in ZONAS.itertuples()],
        "fechas": [f.isoformat() for f in FECHAS],
        "fechas_con_real": [f.isoformat() for f in FECHAS_CON_REAL],
        "cuantiles": CUANTILES,
        "modelo": {"tipo": "XGBoost reg:quantileerror (objetivo en log1p)", "entrenado_hasta": META["fecha_entrenamiento_hasta"],
                   "variables": VARIABLES},
    }


@app.get("/pronostico", summary="Pronóstico de 24 horas para una zona y fecha")
def pronostico(zona_id: int = Query(..., description="ID de la zona (PULocationID)", examples=[161]),
               fecha: date = Query(..., description="Fecha AAAA-MM-DD", examples=["2024-01-25"])):
    if zona_id not in set(ZONAS["PULocationID"]):
        raise HTTPException(status_code=404, detail=f"La zona {zona_id} no se pronostica. Consulte /info para ver las zonas disponibles.")
    filas = demanda[(demanda["PULocationID"] == zona_id) & (demanda["fecha"] == fecha)].sort_values("hora")
    if filas.empty:
        raise HTTPException(status_code=404, detail=f"No hay datos para la fecha {fecha}. Fechas disponibles: {FECHAS[0]} a {FECHAS[-1]}.")

    pred = np.sort(modelo.predict(filas[VARIABLES]), axis=1)  # ordenar evita cuantiles cruzados
    if META.get("transformacion") == "log1p":                  # el modelo se entrenó con log1p(viajes)
        pred = np.expm1(pred)
    pred = np.clip(pred, 0, None)                              # no hay viajes negativos
    zona = ZONAS[ZONAS["PULocationID"] == zona_id].iloc[0]
    horas = []
    for i, fila in enumerate(filas.itertuples()):
        horas.append({
            "hora": int(fila.hora.hour),
            "real": _num(fila.viajes),
            "hace_una_semana": _num(fila.hace_una_semana),
            "cuantiles": {q: round(float(v), 1) for q, v in zip(CUANTILES, pred[i])},
        })
    return {"zona": {"id": int(zona_id), "nombre": zona["zona_nombre"], "distrito": zona["distrito"]},
            "fecha": fecha.isoformat(), "tiene_real": bool(filas["viajes"].notna().any()), "horas": horas}
