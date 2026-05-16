from fastapi import FastAPI, Query, File, UploadFile, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
#from fastapi import Response
import time

from functions import NBAPredictor   # la classe O.O (Orientée Objet)


REQUEST_COUNT = Counter(
    "nba_api_requests_total",
    "Total number of requests",
    ["method", "endpoint", "http_status"]
)

REQUEST_LATENCY = Histogram(
    "nba_api_request_latency_seconds",
    "Request latency in seconds",
    ["endpoint"]
)

# Charger le prédicteur UNE seule fois
predictor = NBAPredictor()


# FastAPI initialization
app = FastAPI(
    title="NBA Prediction API",
    description="API de prédiction NBA by MP DATA",
    version="1.0.0"
)

# CORS autorisé pour tous
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Schéma d'entrée pour prédiction à partir de paramètres
class PlayerStats(BaseModel):
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


# LES ROUTES API

@app.get("/")
def start_server():
    return {"message": "Le serveur NBA prediction conçu par Ketsia MULAPI a démarré !"}


@app.get("/api/nba/predict")
def predict(TOV: float = Query(...),
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
    BLK: float = Query(...),):
    start = time.time()
    status = "200"
    try:
        # ... le code original ...
        arr = predictor.build_params(
        GP, MIN, PTS, FGM, FGA, FGP, PM, PA, PAP,
        FTM, FTA, FTP, OREB, DREB, REB, AST, STL, BLK, TOV
        )

        vect = NBAPredictor.preprocess(arr)
        pred = predictor.predict_vector(vect)

        return {"prediction": pred}
        # return result
    except Exception:
        status = "500"
        raise
    finally:
        elapsed = time.time() - start
        REQUEST_LATENCY.labels(endpoint="/api/nba/predict").observe(elapsed)
        REQUEST_COUNT.labels(method="GET", endpoint="/api/nba/predict", http_status=status).inc()


# def predict_player(TOV: float = Query(...),
#     GP: float = Query(...),
#     MIN: float = Query(...),
#     PTS: float = Query(...),
#     FGM: float = Query(...),
#     FGA: float = Query(...),
#     FGP: float = Query(...),
#     PM: float = Query(...),
#     PA: float = Query(...),
#     PAP: float = Query(...),
#     FTM: float = Query(...),
#     FTA: float = Query(...),
#     FTP: float = Query(...),
#     OREB: float = Query(...),
#     DREB: float = Query(...),
#     REB: float = Query(...),
#     AST: float = Query(...),
#     STL: float = Query(...),
#     BLK: float = Query(...),
# ):

#     arr = predictor.build_params(
#         GP, MIN, PTS, FGM, FGA, FGP, PM, PA, PAP,
#         FTM, FTA, FTP, OREB, DREB, REB, AST, STL, BLK, TOV
#     )

#     vect = NBAPredictor.preprocess(arr)
#     pred = predictor.predict_vector(vect)

#     return {"prediction": pred}


@app.get("/api/nba/info")
def decision_by_name(Name: str = Query(..., description="Nom du joueur")):
    """Prédiction à partir du nom dans le CSV."""
    return predictor.predict_by_name(Name)


@app.post("/api/nba/dataset")
def dataset_classification(file: UploadFile = File(...)):
    """Prédictions vectorisées sur un CSV uploadé."""

    # Vérification du format
    if not file.filename.endswith(".csv"):
        return {"error": "Le fichier doit être un CSV."}

    # Lecture du CSV
    df = pd.read_csv(file.file)

    # Prédictions (batch)
    return predictor.predict_dataset(df)




@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)