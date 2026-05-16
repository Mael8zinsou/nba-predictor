from datetime import datetime
import requests

from airflow import DAG
from airflow.operators.python import PythonOperator

API_BASE = "http://nba-backend-svc.nba.svc.cluster.local:8080"

def call_nba_predict():
    params = {
        "TOV": 2,
        "GP": 82,
        "MIN": 28,
        "PTS": 14,
        "FGM": 5,
        "FGA": 11,
        "FGP": 0.45,
        "PM": 2,
        "PA": 5,
        "PAP": 0.40,
        "FTM": 2,
        "FTA": 3,
        "FTP": 0.67,
        "OREB": 1,
        "DREB": 4,
        "REB": 5,
        "AST": 4,
        "STL": 1,
        "BLK": 0.5
    }

    response = requests.get(
        f"{API_BASE}/api/nba/predict",
        params=params,
        timeout=10
    )
    response.raise_for_status()

    result = response.json()
    print("NBA prediction result:", result)

    return result


with DAG(
    dag_id="nba_orchestration",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["nba", "kubernetes", "ml"],
) as dag:

    predict_task = PythonOperator(
        task_id="call_nba_backend_api",
        python_callable=call_nba_predict,
    )
