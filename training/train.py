"""Pipeline d'entrainement reproductible du modele NBA (Vague 6).

Corrige la dette technique historique :
  - L'ancien classifier.pikl etait serialise avec sklearn 0.24.1 (warning
    InconsistentVersionWarning a chaque chargement) sans scaler associe.
  - L'inference (preprocess()) faisait un Min-Max GLOBAL sur le vecteur unique
    au lieu d'un scaling par-feature fitte sur le dataset (bug documente).

Ce script :
  1. Charge le dataset (ordre de features = celui attendu par l'API)
  2. Split train/test 80/20 reproductible (random_state fixe)
  3. Fit un MinMaxScaler sur le train, transforme train + test
  4. Entraine une LogisticRegression
  5. Evalue sur le test (metriques honnetes, jamais vues a l'entrainement)
  6. Serialise classifier.pikl + scaler.pikl cote API
  7. Logge tout dans MLflow (params, metriques, artefacts)

Usage :
  # Local (MLflow en mode fichier ./mlruns) :
  python training/train.py

  # Vers un serveur MLflow distant (cluster) :
  MLFLOW_TRACKING_URI=http://localhost:5000 python training/train.py

Reproductibilite : meme dataset + meme RANDOM_STATE => meme modele.
"""

from __future__ import annotations

import os
import pickle
from pathlib import Path
from typing import Final

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler

# --- Constantes de reproductibilite ---
RANDOM_STATE: Final = 42
TEST_SIZE: Final = 0.2

# Ordre EXACT des features attendu par l'API (cf. functions.py build_params).
# Identique a l'ordre des colonnes du CSV apres drop de Name + TARGET_5Yrs.
# NE PAS REORDONNER : le modele et l'API doivent partager cet ordre.
FEATURE_ORDER: Final[list[str]] = [
    "GP", "MIN", "PTS", "FGM", "FGA", "FG%", "3P Made", "3PA", "3P%",
    "FTM", "FTA", "FT%", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV",
]  # fmt: skip
TARGET_COL: Final = "TARGET_5Yrs"

# Chemins (relatifs a la racine du repo).
REPO_ROOT: Final = Path(__file__).resolve().parent.parent
DATA_PATH: Final = REPO_ROOT / "nba-api" / "static" / "data" / "nba_logreg.csv"
MODEL_DIR: Final = REPO_ROOT / "nba-api" / "static" / "model"
MODEL_PATH: Final = MODEL_DIR / "classifier.pikl"
SCALER_PATH: Final = MODEL_DIR / "scaler.pikl"


def load_data() -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Charge le dataset, renvoie (X array dans l'ordre des features, y array).

    On renvoie des arrays numpy (pas de DataFrame) pour que le MinMaxScaler
    soit fitté SANS feature_names_in_ : l'API d'inférence travaille en arrays
    numpy nus (cf. build_params), et un scaler fitté avec noms de colonnes
    émettrait un UserWarning à chaque transform sur array nu.
    """
    df = pd.read_csv(DATA_PATH)
    # fillna(0) reproduit le comportement historique (predict_by_name).
    x = df[FEATURE_ORDER].fillna(0).to_numpy(dtype=float)
    y = df[TARGET_COL].to_numpy(dtype=float)
    return x, y


def main() -> None:
    """Entraine, evalue, serialise, et logge dans MLflow."""
    mlflow.set_experiment("nba-career-longevity")

    with mlflow.start_run():
        x, y = load_data()

        x_train, x_test, y_train, y_test = train_test_split(
            x, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
        )

        # Fit le scaler UNIQUEMENT sur le train (pas de fuite de donnees test).
        scaler = MinMaxScaler()
        x_train_scaled = scaler.fit_transform(x_train)
        x_test_scaled = scaler.transform(x_test)

        model = LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)
        model.fit(x_train_scaled, y_train)

        # --- Evaluation sur le test (metriques honnetes) ---
        y_pred = model.predict(x_test_scaled)
        y_proba = model.predict_proba(x_test_scaled)[:, 1]
        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred),
            "recall": recall_score(y_test, y_pred),
            "f1": f1_score(y_test, y_pred),
            "roc_auc": roc_auc_score(y_test, y_proba),
        }

        # --- MLflow tracking ---
        mlflow.log_params(
            {
                "model": "LogisticRegression",
                "max_iter": 1000,
                "random_state": RANDOM_STATE,
                "test_size": TEST_SIZE,
                "scaler": "MinMaxScaler",
                "n_features": len(FEATURE_ORDER),
                "n_train": len(x_train),
                "n_test": len(x_test),
            }
        )
        mlflow.log_metrics(metrics)
        mlflow.sklearn.log_model(model, artifact_path="model")

        # --- Serialisation cote API (consommee par functions.py) ---
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(model, f)
        with open(SCALER_PATH, "wb") as f:
            pickle.dump(scaler, f)

        print("=== Entrainement termine ===")
        print(f"  Dataset : {len(x)} joueurs ({len(x_train)} train / {len(x_test)} test)")
        for name, value in metrics.items():
            print(f"  {name:10s}: {value:.4f}")
        print(f"  Modele  -> {MODEL_PATH.relative_to(REPO_ROOT)}")
        print(f"  Scaler  -> {SCALER_PATH.relative_to(REPO_ROOT)}")
        tracking = os.environ.get("MLFLOW_TRACKING_URI", "./mlruns (local)")
        print(f"  MLflow  -> {tracking}")


if __name__ == "__main__":
    main()
