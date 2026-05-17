"""Configuration pytest globale : ajoute nba-api au sys.path + fixtures partagées."""

import os
import sys
from pathlib import Path

import pytest

# nba-api/ n'est pas un package Python distribué (pas d'__init__.py), donc on
# l'ajoute au sys.path pour pouvoir `from functions import NBAPredictor` et
# `from app import app` dans les tests.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "nba-api"))


@pytest.fixture(autouse=True, scope="session")
def _chdir_to_nba_api() -> None:
    """Bascule le cwd vers nba-api/ pour que les chemins relatifs marchent.

    Le code applicatif fait des chemins relatifs ("static/data/...",
    "static/model/...") qui ne marchent que si on cwd dans nba-api/.
    Pytest met le cwd au rootdir (= racine du repo), ce qui casserait
    NBAPredictor() et predict_by_name() — cette fixture autouse corrige le tir.
    """
    os.chdir(ROOT / "nba-api")
