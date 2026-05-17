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
    def test_output_range_0_1_on_typical_input(self) -> None:
        """L'output est dans [0, 1] pour une entrée standard."""
        from functions import NBAPredictor

        arr = np.array([[10.0, 20.0, 30.0]])
        out = NBAPredictor.preprocess(arr)
        assert out.min() >= 0.0
        assert out.max() <= 1.0

    def test_constant_input_returns_zeros(self) -> None:
        """Si toutes les valeurs sont identiques (min == max), on évite la div par zéro."""
        from functions import NBAPredictor

        arr = np.array([[5.0, 5.0, 5.0]])
        out = NBAPredictor.preprocess(arr)
        # (5-5)/1.0 = 0 partout : pas de NaN, pas d'inf
        assert not np.any(np.isnan(out))
        assert not np.any(np.isinf(out))
        np.testing.assert_array_equal(out, np.zeros_like(arr))

    @pytest.mark.xfail(
        reason=(
            "BUG CONNU : preprocess() calcule min/max sur le vecteur seul (1 ligne x 19 features) "
            "au lieu d'utiliser les statistiques du dataset d'entraînement. Conséquence : "
            "la feature dominante (typiquement GP, 50-82) écrase les autres. "
            "Fix prévu en Vague 6 avec un MinMaxScaler entraîné et sérialisé via MLflow. "
            "Voir memory/project_known_bugs.md."
        ),
        strict=True,
    )
    def test_single_vector_uses_dataset_statistics(self) -> None:
        """Le scaling d'un vecteur unique devrait utiliser les min/max du dataset, pas du vecteur.

        Test rouge volontaire : documente le bug. Quand il sera fixé en V6, ce test
        passera et `strict=True` fera échouer le run (signal pour mettre à jour ce test).
        """
        from functions import NBAPredictor

        # On simule deux joueurs avec des stats très différentes (l'un avec GP=82,
        # l'autre avec GP=10). Si preprocess() utilisait les stats du dataset,
        # les valeurs normalisées seraient cohérentes entre les deux appels.
        player_a = NBAPredictor.build_params(
            GP=82, MIN=28, PTS=14, FGM=5, FGA=11, FGP=0.45, PM=2, PA=5, PAP=0.40,
            FTM=2, FTA=3, FTP=0.67, OREB=1, DREB=4, REB=5, AST=4, STL=1, BLK=0.5, TOV=2,
        )  # fmt: skip
        player_b = NBAPredictor.build_params(
            GP=10, MIN=28, PTS=14, FGM=5, FGA=11, FGP=0.45, PM=2, PA=5, PAP=0.40,
            FTM=2, FTA=3, FTP=0.67, OREB=1, DREB=4, REB=5, AST=4, STL=1, BLK=0.5, TOV=2,
        )  # fmt: skip
        out_a = NBAPredictor.preprocess(player_a)
        out_b = NBAPredictor.preprocess(player_b)
        # La feature MIN (index 1) devrait être identique entre A et B (même valeur 28)
        # si on scalait sur les stats du dataset. Avec le bug actuel, elle est
        # différente parce que les min/max varient selon le GP du joueur.
        assert out_a[0, 1] == pytest.approx(out_b[0, 1])


# ---------------------------------------------------------------------------
# predict_vector : appel modèle direct sur vecteur préprocessé
# ---------------------------------------------------------------------------


class TestPredictVector:
    def test_returns_decision_key(self, predictor: "NBAPredictor") -> None:
        """La réponse contient toujours la clé 'decision'."""
        from functions import NBAPredictor

        arr = NBAPredictor.build_params(*([1.0] * 19))
        vect = NBAPredictor.preprocess(arr)
        result = predictor.predict_vector(vect)
        assert "decision" in result

    def test_decision_is_list_of_floats(self, predictor: "NBAPredictor") -> None:
        """'decision' est une liste de prédictions (1 élément pour 1 vecteur)."""
        from functions import NBAPredictor

        arr = NBAPredictor.build_params(*([1.0] * 19))
        vect = NBAPredictor.preprocess(arr)
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
