"""Logique métier de prédiction NBA : chargement modèle, preprocessing, inférence."""

import pickle  # noqa: S403 -- modèle de confiance, sérialisé en interne
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray


class NBAPredictor:
    """
    Classe centralisée pour gérer les prédictions NBA.
    - Chargement du modèle
    - Normalisation des données
    - Prédictions paramètre par paramètre
    - Prédiction par nom dans un CSV
    """

    def __init__(
        self,
        model_path: str = "static/model/classifier.pikl",
        scaler_path: str = "static/model/scaler.pikl",
    ) -> None:
        """Charge une seule fois le modèle + le scaler sérialisés (Vague 6).

        Le scaler (MinMaxScaler fitté sur le dataset d'entraînement) est
        désormais chargé au démarrage, ce qui corrige le bug historique de
        preprocess() (Min-Max global sur le vecteur unique) et évite de
        re-fitter un scaler à chaque requête (cf. predict_by_name avant V6).
        """
        with open(model_path, "rb") as f:
            self.model: Any = pickle.load(f)  # noqa: S301 -- artefact interne
        with open(scaler_path, "rb") as f:
            self.scaler: Any = pickle.load(f)  # noqa: S301 -- artefact interne

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

    def preprocess(self, arr: NDArray[np.float64]) -> NDArray[np.float64]:
        """Applique le MinMaxScaler entraîné (par-feature) au tableau passé.

        FIX Vague 6 : on applique le scaler fitté sur le dataset d'entraînement
        (chargé au __init__), feature par feature. Chaque colonne est normalisée
        avec le (min, max) de CETTE feature dans le dataset, peu importe le
        nombre de lignes en entrée (1 vecteur ou N).

        Remplace l'ancien comportement bugué : un Min-Max GLOBAL sur l'ensemble
        des valeurs du vecteur (qui écrasait les features de petite échelle
        derrière la feature dominante, typiquement GP). Le scaler garantit la
        cohérence avec la façon dont le modèle a été entraîné.
        """
        return self.scaler.transform(arr)  # type: ignore[no-any-return]

    def predict_vector(self, vect: NDArray[np.float64]) -> dict[str, list[float]]:
        """Renvoie la prédiction brute pour un ou plusieurs vecteurs déjà préprocessés."""
        return {"decision": self.model.predict(vect).tolist()}

    def predict_by_name(self, name: str) -> dict[str, Any]:
        """Recherche le joueur dans le CSV de référence, renvoie la décision.

        Vague 6 : utilise le scaler pré-entraîné (self.scaler) au lieu de
        re-fitter un MinMaxScaler à chaque requête. Plus rapide et cohérent
        avec preprocess() (même scaler partout).
        """
        df = pd.read_csv("static/data/nba_logreg.csv")

        names = df["Name"].tolist()
        df_vals = df.drop(["TARGET_5Yrs", "Name"], axis=1).fillna(0).values

        x = self.scaler.transform(df_vals)

        preds = self.model.predict(x)
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
