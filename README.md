# NBA Predictor — MLOps Pipeline

> Industrialisation cloud-native d'une application ML de classification NBA : conteneurisation, orchestration Kubernetes, automatisation Airflow, observabilité Prometheus/Grafana — déployable en local sur Minikube en quelques commandes.

![Kubernetes](https://img.shields.io/badge/Kubernetes-1.28+-326CE5?logo=kubernetes&logoColor=white)
![Airflow](https://img.shields.io/badge/Apache_Airflow-2.x-017CEE?logo=apacheairflow&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Prometheus](https://img.shields.io/badge/Prometheus-monitoring-E6522C?logo=prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-dashboards-F46800?logo=grafana&logoColor=white)
![Helm](https://img.shields.io/badge/Helm-charts-0F1689?logo=helm&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## Pourquoi ce projet

Une application Machine Learning fonctionnelle (modèle entraîné + API + frontend) ne suffit pas pour la production. Ce projet répond à quatre questions concrètes d'industrialisation :

- **Conteneurisation** — comment isoler proprement une application ML et ses dépendances ?
- **Orchestration** — comment piloter plusieurs composants et automatiser les appels API ?
- **Observabilité** — comment superviser l'infrastructure et les métriques métier en temps réel ?
- **Résilience** — comment diagnostiquer et résoudre les erreurs d'une architecture distribuée ?

Le résultat : un pipeline reproductible, observable et démontrable, représentatif des solutions utilisées en production.

> **Crédit** — l'application NBA initiale (modèle, API, frontend) est l'œuvre de [Ketsia MULAPI](https://github.com/) (juin 2021). La partie industrialisation (Docker, Kubernetes, Airflow, Prometheus, Grafana) a été conçue par **Maël M. ZINSOU** en 2026 dans le cadre du cours "Infrastructures et orchestration de données" (YNOV).

---

## Architecture

L'architecture est cloisonnée par **3 namespaces Kubernetes** déployés sur Minikube :

![Architecture globale](docs/architecture_excalidraw.jpg)

| Namespace | Composants | Rôle |
|---|---|---|
| `nba` | Frontend Nginx + Backend FastAPI | Application métier |
| `airflow` | Apache Airflow (LocalExecutor) + PostgreSQL 16 | Orchestration des appels API |
| `monitoring` | kube-prometheus-stack (Prometheus + Grafana) | Supervision via ServiceMonitor |

### Flux clés

![Flux de communication](docs/flux_excalidraw.jpg)

- **Applicatif** : navigateur → Nginx (reverse proxy `/api/*`) → FastAPI
- **Orchestration** : DAG `nba_orchestration` → `GET /api/nba/predict`
- **Observabilité** : FastAPI `/metrics` → Prometheus → Grafana

---

## Stack

| Composant | Choix | Justification |
|---|---|---|
| Conteneurisation | **Docker** | Isolation, comportement identique dev/prod |
| Orchestration | **Kubernetes (Minikube)** | Standard industriel, déclaratif |
| Backend | **FastAPI** + scikit-learn | Performance, doc OpenAPI auto, intégration Prometheus native |
| Frontend / Reverse proxy | **Nginx** | Statique performant, élimine les problèmes CORS |
| Orchestration de tâches | **Apache Airflow** (Helm, LocalExecutor) | Standard pour DAGs, logs centralisés |
| Base métadonnées Airflow | **PostgreSQL 16** | Robuste, image officielle, déployée séparément du chart |
| Métriques | **Prometheus** (`kube-prometheus-stack`) | Scraping auto via ServiceMonitor |
| Dashboards | **Grafana** | Visualisation infra + métriques métier |

---

## Quickstart

### Prérequis

- [Minikube](https://minikube.sigs.k8s.io/) ≥ 1.30
- [kubectl](https://kubernetes.io/docs/tasks/tools/) ≥ 1.28
- [Helm](https://helm.sh/) ≥ 3.12
- [Docker](https://docs.docker.com/get-docker/) (Desktop ou Engine)

### Déploiement en 6 étapes

```bash
# 1. Démarrer Minikube
minikube start --cpus=4 --memory=8192

# 2. Pointer Docker vers le daemon Minikube (sinon ImagePullBackOff)
eval $(minikube docker-env)         # Linux/macOS
# minikube -p minikube docker-env --shell powershell | Invoke-Expression   # Windows PowerShell

# 3. Build des images applicatives
docker build -t nba-backend:1.1 ./nba-api
docker build -t nba-frontend:1.0 ./nba-web

# 4. Créer les namespaces et déployer l'app NBA
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/

# 5. Déployer la stack monitoring
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install kube-prom prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace

# 6. Déployer Airflow
kubectl create namespace airflow
kubectl apply -f k8s/airflow-postgres.yaml   # Postgres dédié AVANT le chart
helm repo add apache-airflow https://airflow.apache.org
helm install airflow apache-airflow/airflow \
  --namespace airflow -f airflow-values.yaml
```

### Accès aux interfaces

```bash
# Application NBA (frontend)
kubectl port-forward -n nba svc/nba-frontend-svc 8080:80
# → http://localhost:8080

# Airflow UI (admin/admin)
kubectl port-forward -n airflow svc/airflow-api-server 8081:8080
# → http://localhost:8081

# Grafana (admin/prom-operator)
kubectl port-forward -n monitoring svc/kube-prom-grafana 3000:80
# → http://localhost:3000
```

---

## Démonstration

Une fois déployé, le pipeline complet est observable de bout en bout :

1. L'utilisateur fait une prédiction depuis l'interface web
2. Le DAG Airflow `nba_orchestration` peut être déclenché manuellement pour automatiser des appels API
3. Prometheus scrape `/metrics` du backend toutes les 15s
4. Grafana affiche en temps réel le volume de requêtes et la latence

Le rapport complet ([docs/Rapport projet orchestra nba_predictor.pdf](docs/Rapport%20projet%20orchestra%20nba_predictor.pdf)) détaille l'architecture, les choix techniques, les difficultés rencontrées et leur résolution.

---

## Structure du repo

```
nba_predictor/
├── nba-api/                    # Backend FastAPI + modèle ML (voir nba-api/README.md)
├── nba-web/                    # Frontend statique (HTML + jQuery + Bootstrap)
├── k8s/                        # Manifestes Kubernetes
│   ├── namespace.yaml
│   ├── backend-deployment.yaml
│   ├── backend-service.yaml
│   ├── backend-servicemonitor.yaml
│   ├── frontend-deployment.yaml
│   ├── frontend-service.yaml
│   └── airflow-postgres.yaml   # Postgres dédié pour Airflow
├── dags/                       # DAGs Airflow
│   └── nba_orchestration.py
├── airflow-values.yaml         # Values Helm pour Airflow
├── docs/                       # Rapport PDF + schémas Excalidraw
└── README.md                   # Ce fichier
```

---

## Points d'attention techniques

- **Build dans Minikube** — `eval $(minikube docker-env)` est obligatoire avant `docker build` ; les daemons Docker Desktop et Minikube sont séparés.
- **`imagePullPolicy: Never`** — volontaire, car les images sont buildées localement dans le cluster.
- **Label `release: kube-prom`** — requis sur le ServiceMonitor pour que Prometheus le détecte.
- **PostgreSQL d'Airflow déployé séparément** — décision motivée par les instabilités du subchart Postgres du chart Airflow officiel (cf. rapport §6).
- **Pas d'Ingress** — accès via `kubectl port-forward` (NodePort en fallback : 30080 backend, 30081 frontend).

---

## Roadmap

Ce projet est en évolution active vers un vrai showcase Data Engineering. Prochaines étapes :

- [ ] CI/CD GitHub Actions (lint, tests, build, scan Trivy)
- [ ] Tests unitaires (pytest) et d'intégration (kind)
- [ ] Helm chart maison pour le namespace `nba`
- [ ] Secrets K8s via SOPS/sealed-secrets (sortir le password Postgres en dur)
- [ ] Dashboards Grafana versionnés (provisioning via ConfigMap)
- [ ] OpenTelemetry traces (DAG Airflow → API → modèle)
- [ ] Pipeline d'entraînement reproductible (MLflow + DVC)
- [ ] DAG Airflow plus réaliste (scraping stats NBA → enrichissement → prédiction batch)

---

## License

[MIT](LICENSE) — voir le fichier `LICENSE` pour les détails.

Le code applicatif initial est © Ketsia MULAPI 2021. L'industrialisation est © Maël M. ZINSOU 2026.

---

## Contact

Maël M. ZINSOU — [maelzinsou@proton.me](mailto:maelzinsou@proton.me)
