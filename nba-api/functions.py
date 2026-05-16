import pickle
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler


class NBAPredictor:
    """
    Classe centralisée pour gérer les prédictions NBA.
    - Chargement du modèle
    - Normalisation des données
    - Prédictions paramètre par paramètre
    - Prédiction par nom dans un CSV
    """

    def __init__(self, model_path="static/model/classifier.pikl"):
        """Charge une seule fois le modèle."""
        with open(model_path, "rb") as f:
            self.model = pickle.load(f)


    # Préparation des paramètres
    @staticmethod
    def build_params(
        GP, MIN, PTS, FGM, FGA, FGP, PM, PA, PAP,
        FTM, FTA, FTP, OREB, DREB, REB, AST, STL, BLK, TOV
    ):
        """Prépare un array numpy 2D avec les paramètres."""
        return np.array([[
            float(GP), float(MIN), float(PTS), float(FGM), float(FGA),
            float(FGP), float(PM), float(PA), float(PAP),
            float(FTM), float(FTA), float(FTP),
            float(OREB), float(DREB), float(REB),
            float(AST), float(STL), float(BLK), float(TOV)
        ]], dtype=float)

    # Normalisation Min-Max
    @staticmethod
    def preprocess(arr):
        """C'est un normalizez : Min-Max Scaling professionnel."""
        minimum = arr.min()
        maximum = arr.max()
        denom = maximum - minimum if maximum != minimum else 1.0
        return (arr - minimum) / denom

    # Prédiction sur un vecteur prétraité
    def predict_vector(self, vect):
        """Renvoie la prédiction brute."""
        return {"decision":self.model.predict(vect).tolist()}

    # Prédiction à partir de valeurs numériques
    def predict_params(self, *params):
        """Prédit à partir d'un ensemble de paramètres."""
        arr = self.get_params(*params)
        vect = self.preprocess(arr)
        pred = self.predict_vector(vect)[0]
        return {"decision": float(pred)}

    # Prédiction à partir du nom d’un joueur dans le CSV
    def predict_by_name(self, name: str):
        """Recherche le joueur dans le CSV, normalise le dataset et renvoie la décision."""
        df = pd.read_csv("static/data/nba_logreg.csv")

        names = df["Name"].tolist()
        df_vals = df.drop(["TARGET_5Yrs", "Name"], axis=1).fillna(0).values

        # Normalisation MinMax : même chose que preprocess
        X = MinMaxScaler().fit_transform(df_vals)

        # Prédiction
        preds = self.model.predict(X)
        frame = pd.DataFrame({"names": names, "prediction": preds})

        found = frame[frame["names"] == name]

        if found.empty:
            return {"error": f"Joueur '{name}' introuvable"}

        value = float(found["prediction"].values[0])
        return {"decision": [value]}

    
    # Prédiction sur dataset complet (CSV upload)
    def predict_dataset(self, df: pd.DataFrame):
        """Prédiction vectorisée sur plusieurs joueurs."""
        if df.empty:
            return {"error": "Le dataset est vide."}

        vect = self.preprocess(df.values)
        preds = self.model.predict(vect)

        recruit_idx = [i for i, p in enumerate(preds) if p == 1]

        return {
            "total_players": len(preds),
            "recruitable_count": len(recruit_idx),
            "recruitable_positions": recruit_idx,
            "decision": preds.tolist()
        }
