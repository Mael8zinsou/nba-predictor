# NBA Predictor — Backend API

API REST de classification de joueurs NBA, basée sur **FastAPI** et un modèle de **régression logistique** pré-entraîné.

> **Crédit auteur initial :** l'application (modèle, dataset, code FastAPI, frontend) a été conçue par **Ketsia MULAPI** en juin 2021 dans le cadre d'un exercice de classification ML. La partie industrialisation (Docker, Kubernetes, Airflow, Prometheus) a été ajoutée par **Maël M. ZINSOU** en 2026. Voir le [README racine](../README.md) pour la vue d'ensemble du projet d'orchestration.

---

## Objectif

À partir des statistiques sportives d'un joueur NBA débutant (19 features : points par match, rebonds, passes décisives, pourcentages de tir, etc.), prédire s'il a le potentiel de **durer plus de 5 ans en NBA** — autrement dit, s'il vaut le coup d'investir.

Cas d'usage : aide à la décision pour recruteurs et investisseurs cherchant à capitaliser sur de futurs talents.

## Modèle

- **Algorithme :** régression logistique (`scikit-learn`)
- **Dataset :** `static/data/nba_logreg.csv` (statistiques de joueurs NBA débutants, target binaire `TARGET_5Yrs`)
- **Artefact :** `static/model/classifier.pikl` (modèle sérialisé, chargé une fois au démarrage de l'API)

## Endpoints

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/` | Healthcheck simple |
| `GET` | `/docs` | Documentation OpenAPI interactive (Swagger UI) |
| `GET` | `/redoc` | Documentation OpenAPI alternative (ReDoc) |
| `GET` | `/api/nba/predict` | Prédiction à partir des 19 statistiques en query params |
| `GET` | `/api/nba/info?Name=<nom>` | Prédiction à partir du nom d'un joueur présent dans le dataset |
| `POST` | `/api/nba/dataset` | Prédictions batch sur un CSV uploadé (multipart/form-data) |
| `GET` | `/metrics` | Métriques Prometheus (compteurs de requêtes, latence) |

### Features attendues par `/api/nba/predict`

`GP`, `MIN`, `PTS`, `FGM`, `FGA`, `FGP`, `PM`, `PA`, `PAP`, `FTM`, `FTA`, `FTP`, `OREB`, `DREB`, `REB`, `AST`, `STL`, `BLK`, `TOV`

Toutes sont des `float` obligatoires (query parameters).

## Lancement en local (hors Kubernetes)

```bash
# Depuis le dossier nba-api/
pip install -r requirements.txt
uvicorn app:app --reload --port 8080
```

Ouvrir ensuite :
- Documentation interactive : <http://localhost:8080/docs>
- Test rapide par nom : <http://localhost:8080/api/nba/info?Name=LeBron%20James>
- Test rapide par features :
  <http://localhost:8080/api/nba/predict?TOV=2&GP=82&MIN=28&PTS=14&FGM=5&FGA=11&FGP=0.45&PM=2&PA=5&PAP=0.40&FTM=2&FTA=3&FTP=0.67&OREB=1&DREB=4&REB=5&AST=4&STL=1&BLK=0.5>

Réponse type :
```json
{"prediction": {"decision": [1.0]}}
```

`1.0` → joueur recrutable, `0.0` → non recrutable.

## Lancement via Docker

```bash
docker build -t nba-backend:1.1 .
docker run -p 8080:8080 nba-backend:1.1
```

## Lancement via Kubernetes

Voir le [README racine](../README.md) pour le déploiement complet (frontend + Airflow + monitoring).

## Structure du dossier

```
nba-api/
├── app.py              # Routes FastAPI + instrumentation Prometheus
├── functions.py        # Classe NBAPredictor (chargement modèle, preprocessing, inférence)
├── requirements.txt    # Dépendances Python
├── Dockerfile          # Image backend
├── .dockerignore
└── static/
    ├── data/nba_logreg.csv    # Dataset d'entraînement
    └── model/classifier.pikl  # Modèle sérialisé
```

## Tests rapides avec curl ou Postman

```bash
# Par nom
curl "http://localhost:8080/api/nba/info?Name=LeBron%20James"

# Par features
curl "http://localhost:8080/api/nba/predict?TOV=2&GP=82&MIN=28&PTS=14&FGM=5&FGA=11&FGP=0.45&PM=2&PA=5&PAP=0.40&FTM=2&FTA=3&FTP=0.67&OREB=1&DREB=4&REB=5&AST=4&STL=1&BLK=0.5"

# Batch CSV
curl -X POST "http://localhost:8080/api/nba/dataset" -F "file=@static/data/nba_logreg.csv"
```
