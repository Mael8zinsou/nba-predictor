"""Tests unitaires de NBAPredictor (nba-api/functions.py).

Approche : on instancie un vrai NBAPredictor (le modèle pickle est petit, ~5 Ko,
load instantané). Pas de mock du modèle — on teste le code applicatif autour,
pas la justesse des prédictions ML.

Pour les prédictions ML elles-mêmes, voir le bug `preprocess()` documenté en
xfail dans test_preprocess_bug() et l'item Vague 6 de la roadmap.
"""

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import pytest

if TYPE_CHECKING:
    from functions import NBAPredictor


@pytest.fixture(scope="module")
def predictor() -> "NBAPredictor":
    """Instance partagée du predictor (chargement du pickle = une fois)."""
    from functions import NBAPredictor

    return NBAPredictor()


# ---------------------------------------------------------------------------
# build_params : conversion 19 floats -> numpy array (1, 19)
# ---------------------------------------------------------------------------


class TestBuildParams:
    def test_shape_is_1_by_19(self) -> None:
        """L'array retourné a toujours la forme (1, 19) pour un seul joueur."""
        from functions import NBAPredictor

        arr = NBAPredictor.build_params(*([1.0] * 19))
        assert arr.shape == (1, 19)

    def test_dtype_is_float(self) -> None:
        """Tous les éléments sont des float64 (pour scikit-learn)."""
        from functions import NBAPredictor

        arr = NBAPredictor.build_params(*([1.0] * 19))
        assert arr.dtype == np.float64

    def test_accepts_int_inputs(self) -> None:
        """Les entrées int sont converties en float (vu que l'API reçoit aussi des entiers)."""
        from functions import NBAPredictor

        arr = NBAPredictor.build_params(*([1] * 19))  # type: ignore[arg-type]
        assert arr.dtype == np.float64
        assert arr[0, 0] == 1.0

    def test_preserves_order_of_args(self) -> None:
        """L'ordre des features dans l'array correspond à l'ordre des arguments."""
        from functions import NBAPredictor

        # build_params(GP, MIN, PTS, FGM, FGA, FGP, PM, PA, PAP, FTM, FTA, FTP,
        #              OREB, DREB, REB, AST, STL, BLK, TOV)
        # On passe des valeurs distinctes pour vérifier qu'aucun argument n'est
        # mélangé. GP=10, MIN=20, ..., TOV=190.
        values = [float(i * 10) for i in range(1, 20)]
        arr = NBAPredictor.build_params(*values)
        np.testing.assert_array_equal(arr[0], values)


# ---------------------------------------------------------------------------
# preprocess : Min-Max scaling
# ---------------------------------------------------------------------------


class TestPreprocess:
    """preprocess() applique désormais le MinMaxScaler entraîné (Vague 6).

    C'est une méthode d'instance (utilise self.scaler chargé au __init__),
    plus une méthode statique. Le scaling est par-feature, fitté sur le
    dataset d'entraînement.
    """

    def test_single_vector_uses_dataset_statistics(self, predictor: "NBAPredictor") -> None:
        """FIX V6 : le scaling utilise les stats du dataset (scaler), pas du vecteur.

        Ce test documentait un bug en xfail strict avant V6. Maintenant que
        preprocess() applique le scaler pré-entraîné, la feature MIN (index 1)
        est normalisée de façon identique quel que soit le GP du joueur :
        elle ne dépend que de la valeur MIN elle-même et des stats dataset.
        """
        from functions import NBAPredictor

        # Deux joueurs identiques sauf GP (82 vs 10). Avec un scaler par-feature,
        # la colonne MIN (=28 pour les deux) doit donner la même valeur normalisée.
        player_a = NBAPredictor.build_params(
            GP=82, MIN=28, PTS=14, FGM=5, FGA=11, FGP=0.45, PM=2, PA=5, PAP=0.40,
            FTM=2, FTA=3, FTP=0.67, OREB=1, DREB=4, REB=5, AST=4, STL=1, BLK=0.5, TOV=2,
        )  # fmt: skip
        player_b = NBAPredictor.build_params(
            GP=10, MIN=28, PTS=14, FGM=5, FGA=11, FGP=0.45, PM=2, PA=5, PAP=0.40,
            FTM=2, FTA=3, FTP=0.67, OREB=1, DREB=4, REB=5, AST=4, STL=1, BLK=0.5, TOV=2,
        )  # fmt: skip
        out_a = predictor.preprocess(player_a)
        out_b = predictor.preprocess(player_b)
        # MIN identique (28) -> même valeur normalisée, indépendamment du GP.
        assert out_a[0, 1] == pytest.approx(out_b[0, 1])

    def test_preserves_shape(self, predictor: "NBAPredictor") -> None:
        """Le scaler conserve la forme (n_samples, 19)."""
        from functions import NBAPredictor

        arr = NBAPredictor.build_params(*([5.0] * 19))
        out = predictor.preprocess(arr)
        assert out.shape == (1, 19)

    def test_no_nan_no_inf(self, predictor: "NBAPredictor") -> None:
        """Pas de NaN ni d'inf en sortie, même sur des valeurs extrêmes."""
        from functions import NBAPredictor

        arr = NBAPredictor.build_params(*([0.0] * 19))
        out = predictor.preprocess(arr)
        assert not np.any(np.isnan(out))
        assert not np.any(np.isinf(out))


# ---------------------------------------------------------------------------
# predict_vector : appel modèle direct sur vecteur préprocessé
# ---------------------------------------------------------------------------


class TestPredictVector:
    def test_returns_decision_key(self, predictor: "NBAPredictor") -> None:
        """La réponse contient toujours la clé 'decision'."""
        from functions import NBAPredictor

        arr = NBAPredictor.build_params(*([1.0] * 19))
        vect = predictor.preprocess(arr)
        result = predictor.predict_vector(vect)
        assert "decision" in result

    def test_decision_is_list_of_floats(self, predictor: "NBAPredictor") -> None:
        """'decision' est une liste de prédictions (1 élément pour 1 vecteur)."""
        from functions import NBAPredictor

        arr = NBAPredictor.build_params(*([1.0] * 19))
        vect = predictor.preprocess(arr)
        result = predictor.predict_vector(vect)
        assert isinstance(result["decision"], list)
        assert len(result["decision"]) == 1


# ---------------------------------------------------------------------------
# predict_by_name : recherche dans le dataset CSV
# ---------------------------------------------------------------------------


class TestPredictByName:
    def test_known_player_returns_decision(self, predictor: "NBAPredictor") -> None:
        """Un joueur présent dans le dataset renvoie une décision."""
        result = predictor.predict_by_name("Brandon Ingram")
        assert "decision" in result
        assert "error" not in result
        assert len(result["decision"]) == 1
        # La décision est 0.0 ou 1.0 (classification binaire)
        assert result["decision"][0] in (0.0, 1.0)

    def test_unknown_player_returns_error(self, predictor: "NBAPredictor") -> None:
        """Un joueur absent renvoie une erreur explicite."""
        result = predictor.predict_by_name("Joueur Inexistant XYZ")
        assert "error" in result
        assert "introuvable" in result["error"]
        assert "Joueur Inexistant XYZ" in result["error"]

    def test_empty_name_returns_error(self, predictor: "NBAPredictor") -> None:
        """Une chaîne vide ne match aucun joueur (pas un crash)."""
        result = predictor.predict_by_name("")
        assert "error" in result

    def test_case_sensitive_match(self, predictor: "NBAPredictor") -> None:
        """La recherche est sensible à la casse (comportement actuel à documenter)."""
        result_lower = predictor.predict_by_name("brandon ingram")
        assert "error" in result_lower  # "brandon" != "Brandon" dans le dataset


# ---------------------------------------------------------------------------
# predict_dataset : prédiction batch sur un DataFrame uploadé
# ---------------------------------------------------------------------------


class TestPredictDataset:
    def test_empty_dataframe_returns_error(self, predictor: "NBAPredictor") -> None:
        """Un DataFrame vide renvoie une erreur explicite."""
        result = predictor.predict_dataset(pd.DataFrame())
        assert "error" in result
        assert "vide" in result["error"]

    def test_returns_expected_keys(self, predictor: "NBAPredictor") -> None:
        """La réponse batch contient les 4 clés attendues."""
        df = pd.DataFrame([[1.0] * 19] * 3)  # 3 joueurs, 19 features chacun
        result = predictor.predict_dataset(df)
        assert set(result.keys()) == {
            "total_players",
            "recruitable_count",
            "recruitable_positions",
            "decision",
        }

    def test_total_players_matches_input_size(self, predictor: "NBAPredictor") -> None:
        """total_players reflète bien le nombre de lignes du DataFrame."""
        df = pd.DataFrame([[1.0] * 19] * 5)
        result = predictor.predict_dataset(df)
        assert result["total_players"] == 5
        assert len(result["decision"]) == 5

    def test_recruitable_count_consistent(self, predictor: "NBAPredictor") -> None:
        """recruitable_count est cohérent avec recruitable_positions et decision."""
        df = pd.DataFrame([[1.0] * 19] * 4)
        result = predictor.predict_dataset(df)
        assert result["recruitable_count"] == len(result["recruitable_positions"])
        # Tous les indices recruitable doivent avoir decision=1
        for idx in result["recruitable_positions"]:
            assert result["decision"][idx] == 1
