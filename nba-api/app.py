"""FastAPI app exposant les routes de prédiction NBA + métriques Prometheus."""

import time
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from functions import NBAPredictor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

# --- Métriques Prometheus ---
REQUEST_COUNT = Counter(
    "nba_api_requests_total",
    "Total number of requests",
    ["method", "endpoint", "http_status"],
)

REQUEST_LATENCY = Histogram(
    "nba_api_request_latency_seconds",
    "Request latency in seconds",
    ["endpoint"],
)

# Charger le prédicteur UNE seule fois au démarrage du worker uvicorn
predictor = NBAPredictor()

app = FastAPI(
    title="NBA Prediction API",
    description="API de prédiction NBA — classification 5-Year Career Longevity",
    version="1.0.0",
)

# CORS large pour le contexte local/démo. Le frontend nginx fait le reverse-proxy
# et les requêtes navigateur passent par /api/* (même origine), donc CORS sert
# principalement aux appels Postman / curl / DAG Airflow.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlayerStats(BaseModel):
    """Schéma Pydantic pour une fiche statistique de joueur NBA (19 features)."""

    GP: float
    MIN: float
    PTS: float
    FGM: float
    FGA: float
    FGP: float
    PM: float
    PA: float
    PAP: float
    FTM: float
    FTA: float
    FTP: float
    OREB: float
    DREB: float
    REB: float
    AST: float
    STL: float
    BLK: float
    TOV: float


# --- Routes ---


@app.get("/")
def start_server() -> dict[str, str]:
    """Healthcheck minimal — confirme que l'API répond."""
    return {"message": "Le serveur NBA prediction conçu par Ketsia MULAPI a démarré !"}


@app.get("/api/nba/predict")
def predict(
    TOV: float = Query(...),
    GP: float = Query(...),
    MIN: float = Query(...),
    PTS: float = Query(...),
    FGM: float = Query(...),
    FGA: float = Query(...),
    FGP: float = Query(...),
    PM: float = Query(...),
    PA: float = Query(...),
    PAP: float = Query(...),
    FTM: float = Query(...),
    FTA: float = Query(...),
    FTP: float = Query(...),
    OREB: float = Query(...),
    DREB: float = Query(...),
    REB: float = Query(...),
    AST: float = Query(...),
    STL: float = Query(...),
    BLK: float = Query(...),
) -> dict[str, Any]:
    """Prédit la classe d'un joueur à partir de ses 19 statistiques."""
    start = time.time()
    status = "200"
    try:
        arr = predictor.build_params(
            GP, MIN, PTS, FGM, FGA, FGP, PM, PA, PAP,
            FTM, FTA, FTP, OREB, DREB, REB, AST, STL, BLK, TOV,
        )  # fmt: skip
        vect = NBAPredictor.preprocess(arr)
        pred = predictor.predict_vector(vect)
        return {"prediction": pred}
    except Exception:
        status = "500"
        raise
    finally:
        elapsed = time.time() - start
        REQUEST_LATENCY.labels(endpoint="/api/nba/predict").observe(elapsed)
        REQUEST_COUNT.labels(method="GET", endpoint="/api/nba/predict", http_status=status).inc()


@app.get("/api/nba/info")
def decision_by_name(Name: str = Query(..., description="Nom du joueur")) -> dict[str, Any]:
    """Prédiction à partir du nom dans le CSV de référence."""
    return predictor.predict_by_name(Name)


@app.post("/api/nba/dataset")
def dataset_classification(file: UploadFile = File(...)) -> dict[str, Any]:
    """Prédictions vectorisées sur un CSV uploadé."""
    if not file.filename or not file.filename.endswith(".csv"):
        return {"error": "Le fichier doit être un CSV."}

    df = pd.read_csv(file.file)
    return predictor.predict_dataset(df)


@app.get("/metrics")
def metrics() -> Response:
    """Expose les métriques Prometheus pour scraping par ServiceMonitor."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
