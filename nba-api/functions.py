"""Logique métier de prédiction NBA : chargement modèle, preprocessing, inférence."""

import pickle  # noqa: S403 -- modèle de confiance, sérialisé en interne
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.preprocessing import MinMaxScaler


class NBAPredictor:
    """
    Classe centralisée pour gérer les prédictions NBA.
    - Chargement du modèle
    - Normalisation des données
    - Prédictions paramètre par paramètre
    - Prédiction par nom dans un CSV
    """

    def __init__(self, model_path: str = "static/model/classifier.pikl") -> None:
        """Charge une seule fois le modèle sérialisé pickle."""
        with open(model_path, "rb") as f:
            self.model: Any = pickle.load(f)  # noqa: S301 -- artefact interne

    @staticmethod
    def build_params(
        GP: float,
        MIN: float,
        PTS: float,
        FGM: float,
        FGA: float,
        FGP: float,
        PM: float,
        PA: float,
        PAP: float,
        FTM: float,
        FTA: float,
        FTP: float,
        OREB: float,
        DREB: float,
        REB: float,
        AST: float,
        STL: float,
        BLK: float,
        TOV: float,
    ) -> NDArray[np.float64]:
        """Prépare un array numpy 2D (1, 19) avec les statistiques d'un joueur."""
        return np.array(
            [
                [
                    float(GP),
                    float(MIN),
                    float(PTS),
                    float(FGM),
                    float(FGA),
                    float(FGP),
                    float(PM),
                    float(PA),
                    float(PAP),
                    float(FTM),
                    float(FTA),
                    float(FTP),
                    float(OREB),
                    float(DREB),
                    float(REB),
                    float(AST),
                    float(STL),
                    float(BLK),
                    float(TOV),
                ]
            ],
            dtype=float,
        )

    @staticmethod
    def preprocess(arr: NDArray[np.float64]) -> NDArray[np.float64]:
        """Min-Max scaling sur les valeurs du tableau passé.

        BUG CONNU : sur un vecteur unique (route /api/nba/predict), calcule
        min/max sur les 19 features du vecteur seul, pas sur les statistiques
        du dataset d'entraînement. Voir project_known_bugs.md — fix prévu en
        Vague 6 avec un MinMaxScaler entraîné et sérialisé via MLflow.
        """
        minimum = arr.min()
        maximum = arr.max()
        denom = maximum - minimum if maximum != minimum else 1.0
        return (arr - minimum) / denom  # type: ignore[no-any-return]

    def predict_vector(self, vect: NDArray[np.float64]) -> dict[str, list[float]]:
        """Renvoie la prédiction brute pour un ou plusieurs vecteurs déjà préprocessés."""
        return {"decision": self.model.predict(vect).tolist()}

    def predict_by_name(self, name: str) -> dict[str, Any]:
        """Recherche le joueur dans le CSV, normalise le dataset complet, renvoie la décision.

        Approche correcte au niveau du scaling (fit sur tout le dataset),
        mais inefficace : le scaler est re-fitté à chaque requête. À optimiser
        en Vague 6 avec un scaler pré-entraîné chargé au démarrage.
        """
        df = pd.read_csv("static/data/nba_logreg.csv")

        names = df["Name"].tolist()
        df_vals = df.drop(["TARGET_5Yrs", "Name"], axis=1).fillna(0).values

        # Normalisation MinMax sur le dataset complet (fit + transform)
        X = MinMaxScaler().fit_transform(df_vals)

        preds = self.model.predict(X)
        frame = pd.DataFrame({"names": names, "prediction": preds})
        found = frame[frame["names"] == name]

        if found.empty:
            return {"error": f"Joueur '{name}' introuvable"}

        value = float(found["prediction"].to_numpy()[0])
        return {"decision": [value]}

    def predict_dataset(self, df: pd.DataFrame) -> dict[str, Any]:
        """Prédiction vectorisée sur plusieurs joueurs depuis un DataFrame uploadé."""
        if df.empty:
            return {"error": "Le dataset est vide."}

        vect = self.preprocess(df.to_numpy())
        preds = self.model.predict(vect)

        recruit_idx = [i for i, p in enumerate(preds) if p == 1]

        return {
            "total_players": len(preds),
            "recruitable_count": len(recruit_idx),
            "recruitable_positions": recruit_idx,
            "decision": preds.tolist(),
        }
