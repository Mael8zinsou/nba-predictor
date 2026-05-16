# NBA Predictor — Orchestration & Infrastructure

Projet d'industrialisation d'une application ML de classification de joueurs NBA (cours "Infrastructures et orchestration de données", YNOV, Ketsia Mulapi Tita). Auteur de la partie orchestration/infra : Maël M. ZINSOU. Le code applicatif original (API + frontend) est de Ketsia Mulapi ; le rapport de référence est [docs/Rapport projet orchestra nba_predictor.pdf](docs/Rapport projet orchestra nba_predictor.pdf).

L'objectif n'est pas le modèle ML (régression logistique simple, déjà entraînée et sérialisée dans `classifier.pikl`), mais le **pipeline d'industrialisation** : conteneurisation, orchestration Kubernetes, automatisation Airflow, observabilité Prometheus/Grafana.

## Stack & architecture

Déploiement local via **Minikube**, organisé en 3 namespaces Kubernetes :

| Namespace | Composants | Rôle |
|---|---|---|
| `nba` | Frontend Nginx + Backend FastAPI | Application métier |
| `airflow` | Airflow (LocalExecutor, via Helm) + PostgreSQL 16 dédié | Orchestration des appels API |
| `monitoring` | kube-prometheus-stack (Prometheus + Grafana) | Supervision via ServiceMonitor |

Flux clés :
- **Applicatif** : navigateur → Nginx (reverse proxy `/api/*`) → FastAPI ML
- **Orchestration** : DAG `nba_orchestration` → `GET /api/nba/predict`
- **Observabilité** : FastAPI `/metrics` → Prometheus (scrape via ServiceMonitor avec `release: kube-prom`) → Grafana

## Layout du repo

- [nba-api/](nba-api/) — backend FastAPI (`app.py`, `functions.py:NBAPredictor`), Dockerfile, modèle sérialisé dans `static/model/classifier.pikl`, dataset dans `static/data/nba_logreg.csv`.
- [nba-web/](nba-web/) — frontend statique (HTML + Bootstrap + jQuery) servi par Nginx, avec `nginx.conf` qui fait reverse-proxy vers `nba-backend-svc.nba.svc.cluster.local:8080`.
- [k8s/](k8s/) — manifestes : `namespace.yaml`, `backend-deployment.yaml` / `backend-service.yaml` / `backend-servicemonitor.yaml`, `frontend-deployment.yaml` / `frontend-service.yaml`, `airflow-postgres.yaml` (PVC + Deployment + Service Postgres 16 pour Airflow).
- [dags/](dags/) — DAGs Airflow (`nba_orchestration.py`).
- [airflow-values.yaml](airflow-values.yaml) — values Helm pour Airflow (LocalExecutor, Postgres externe, persistance DAGs + logs).
- [docs/](docs/) — rapport PDF + schémas Excalidraw (architecture et flux).
- `minikube-linux-amd64` — binaire Minikube (Linux) à la racine. Pas de cibles de build.

## Conventions et points d'attention

- **Images Docker buildées dans Minikube** : `eval $(minikube docker-env)` avant `docker build`, sinon `ImagePullBackOff` (les démons Docker Desktop et Minikube sont séparés). `imagePullPolicy: Never` est volontaire dans [k8s/backend-deployment.yaml](k8s/backend-deployment.yaml) pour cette raison.
- **Tags d'image en dur** : `nba-backend:1.1` et `nba-frontend:1.0`. Si rebuild, garder ou bumper les tags dans les manifestes.
- **CORS volontairement géré côté Nginx** (pas dans FastAPI en prod) : le frontend doit toujours appeler des chemins relatifs `/api/*`, jamais `localhost:8080`.
- **ServiceMonitor → label `release: kube-prom` obligatoire** : sans ce label, Prometheus ne scrape pas (cf. section 6 du rapport, problème rencontré et résolu).
- **PostgreSQL d'Airflow déployé séparément** (pas le subchart) : décision motivée par les instabilités du chart Airflow officiel sur le subchart Postgres + PVC. Le password `airflow/airflow/airflow` est en dur dans [k8s/airflow-postgres.yaml](k8s/airflow-postgres.yaml) — acceptable pour ce contexte local/pédagogique uniquement.
- **Métriques Prometheus exposées dans [nba-api/app.py](nba-api/app.py)** : `nba_api_requests_total` (Counter) et `nba_api_request_latency_seconds` (Histogram), via `/metrics`. C'est l'une des deux modifications principales du code source initial (l'autre étant le passage du frontend en chemins relatifs).
- **Accès local via `kubectl port-forward`**, pas d'Ingress configuré. Services exposés en NodePort (`30080` backend, `30081` frontend) pour fallback.
- **Le modèle ML est figé** : `classifier.pikl` est un artefact pré-entraîné, pas de pipeline d'entraînement dans ce repo. Le scope du projet s'arrête à l'inférence et son industrialisation.

## Environnement de dev

- Plateforme principale : **Windows + PowerShell** (utiliser la syntaxe PowerShell pour les commandes). Le binaire Minikube présent est `minikube-linux-amd64` — probablement utilisé dans WSL ou une VM Linux.
- Python 3.10 pour le backend (cf. [nba-api/Dockerfile](nba-api/Dockerfile)).
- Pour tester l'API en local hors K8s : `cd nba-api ; uvicorn app:app --reload --port 8080` puis ouvrir `http://localhost:8080/docs`.

## Ce que je ne dois PAS faire sans confirmation

- Modifier le code de Ketsia (`functions.py`, structure de l'API, frontend HTML/JS) sauf demande explicite — l'évaluation porte sur l'orchestration, pas sur la refonte de l'app.
- Toucher au modèle `classifier.pikl` ou au dataset `nba_logreg.csv`.
- "Nettoyer" le frontend (CSS inline, jQuery, etc.) : c'est tel quel volontairement.
- Supprimer les `__pycache__/` ou autres caches versionnés — vérifier d'abord ce qui est effectivement utile.
