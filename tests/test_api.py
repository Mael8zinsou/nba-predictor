"""Tests d'intégration FastAPI via TestClient (in-process, pas de serveur HTTP).

TestClient utilise httpx en backend pour appeler l'app sans démarrer uvicorn.
On vérifie : codes HTTP, format JSON, présence des métriques Prometheus,
gestion des erreurs.
"""

import io
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    pass


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Client FastAPI partagé pour tous les tests du module."""
    from app import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# Healthcheck
# ---------------------------------------------------------------------------


class TestRoot:
    def test_root_returns_200(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200

    def test_root_returns_json_with_message(self, client: TestClient) -> None:
        response = client.get("/")
        assert "message" in response.json()


# ---------------------------------------------------------------------------
# /api/nba/predict
# ---------------------------------------------------------------------------


VALID_PLAYER_PARAMS = {
    "TOV": 2, "GP": 82, "MIN": 28, "PTS": 14,
    "FGM": 5, "FGA": 11, "FGP": 0.45,
    "PM": 2, "PA": 5, "PAP": 0.40,
    "FTM": 2, "FTA": 3, "FTP": 0.67,
    "OREB": 1, "DREB": 4, "REB": 5,
    "AST": 4, "STL": 1, "BLK": 0.5,
}  # fmt: skip


class TestPredict:
    def test_valid_params_return_200(self, client: TestClient) -> None:
        response = client.get("/api/nba/predict", params=VALID_PLAYER_PARAMS)
        assert response.status_code == 200

    def test_response_structure(self, client: TestClient) -> None:
        response = client.get("/api/nba/predict", params=VALID_PLAYER_PARAMS)
        body = response.json()
        assert "prediction" in body
        assert "decision" in body["prediction"]
        assert isinstance(body["prediction"]["decision"], list)

    def test_missing_param_returns_422(self, client: TestClient) -> None:
        """FastAPI valide les Query params : un paramètre manquant => 422 Unprocessable Entity."""
        incomplete = dict(VALID_PLAYER_PARAMS)
        del incomplete["GP"]
        response = client.get("/api/nba/predict", params=incomplete)
        assert response.status_code == 422

    def test_invalid_type_returns_422(self, client: TestClient) -> None:
        """Un paramètre non castable en float => 422."""
        bad = dict(VALID_PLAYER_PARAMS)
        bad["GP"] = "not_a_number"  # type: ignore[assignment]
        response = client.get("/api/nba/predict", params=bad)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# /api/nba/info?Name=...
# ---------------------------------------------------------------------------


class TestInfo:
    def test_known_player_returns_200(self, client: TestClient) -> None:
        response = client.get("/api/nba/info", params={"Name": "Brandon Ingram"})
        assert response.status_code == 200
        assert "decision" in response.json()

    def test_unknown_player_returns_200_with_error(self, client: TestClient) -> None:
        """L'API renvoie un 200 avec un champ 'error' dans le body (pas un 404).

        C'est le comportement actuel du code legacy de Ketsia : on le documente
        plutôt que de le changer (cohérent avec le contrat consommé par le
        frontend qui s'attend à recevoir un JSON et regarde response.error).
        """
        response = client.get("/api/nba/info", params={"Name": "Joueur XYZ"})
        assert response.status_code == 200
        body = response.json()
        assert "error" in body
        assert "introuvable" in body["error"]

    def test_missing_name_returns_422(self, client: TestClient) -> None:
        response = client.get("/api/nba/info")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# /api/nba/dataset (POST avec upload CSV)
# ---------------------------------------------------------------------------


class TestDataset:
    def test_valid_csv_returns_200(self, client: TestClient) -> None:
        """Upload d'un mini CSV avec 2 joueurs (19 colonnes)."""
        csv_content = (
            "GP,MIN,PTS,FGM,FGA,FGP,PM,PA,PAP,FTM,FTA,FTP,OREB,DREB,REB,AST,STL,BLK,TOV\n"
            "82,28,14,5,11,0.45,2,5,0.40,2,3,0.67,1,4,5,4,1,0.5,2\n"
            "60,20,10,4,9,0.40,1,3,0.33,1,2,0.50,1,3,4,3,1,0.3,1\n"
        )
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        response = client.post("/api/nba/dataset", files=files)
        assert response.status_code == 200
        body = response.json()
        assert body["total_players"] == 2
        assert len(body["decision"]) == 2

    def test_non_csv_extension_returns_error_in_body(self, client: TestClient) -> None:
        """Un fichier non-CSV renvoie un 200 avec error (comportement legacy)."""
        files = {"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")}
        response = client.post("/api/nba/dataset", files=files)
        assert response.status_code == 200
        assert "error" in response.json()

    def test_missing_file_returns_422(self, client: TestClient) -> None:
        response = client.post("/api/nba/dataset")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# /metrics (Prometheus exposition)
# ---------------------------------------------------------------------------


class TestMetrics:
    def test_metrics_endpoint_returns_200(self, client: TestClient) -> None:
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_content_type_is_prometheus(self, client: TestClient) -> None:
        """Le content-type doit être text/plain version=0.0.4 (format Prometheus exposition)."""
        response = client.get("/metrics")
        assert "text/plain" in response.headers["content-type"]
        assert "version=" in response.headers["content-type"]

    def test_custom_metrics_present(self, client: TestClient) -> None:
        """Nos 2 métriques custom doivent apparaître dans l'export."""
        response = client.get("/metrics")
        body = response.text
        assert "nba_api_requests_total" in body
        assert "nba_api_request_latency_seconds" in body

    def test_request_count_increments(self, client: TestClient) -> None:
        """Faire un appel /api/nba/predict doit incrémenter le counter."""
        # Snapshot avant
        before = client.get("/metrics").text

        # Trigger une requête sur /api/nba/predict
        client.get("/api/nba/predict", params=VALID_PLAYER_PARAMS)

        after = client.get("/metrics").text

        # Le counter pour cet endpoint doit avoir augmenté
        # (on regarde juste qu'au moins une ligne nba_api_requests_total avec
        # endpoint="/api/nba/predict" existe en "after" — précis sans parser le format)
        assert "nba_api_requests_total" in after
        assert 'endpoint="/api/nba/predict"' in after
        assert before != after  # quelque chose a changé
