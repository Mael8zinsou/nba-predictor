# NBA Predictor — MLOps Pipeline

> Industrialisation cloud-native d'une application ML de classification NBA : conteneurisation, orchestration Kubernetes, automatisation Airflow, observabilité Prometheus/Grafana — déployable en local sur un cluster [kind](https://kind.sigs.k8s.io/) en quelques commandes.

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

L'architecture est cloisonnée par **3 namespaces Kubernetes** déployés sur un cluster local [kind](https://kind.sigs.k8s.io/) (Kubernetes-in-Docker) :

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
| Conteneurisation | **Docker Desktop** | Isolation, comportement identique dev/prod, host des conteneurs kind |
| Orchestration | **Kubernetes via [kind](https://kind.sigs.k8s.io/)** | Cluster local rapide, sans VM, conteneurs visibles dans Docker Desktop |
| Backend | **FastAPI** + scikit-learn | Performance, doc OpenAPI auto, intégration Prometheus native |
| Frontend / Reverse proxy | **Nginx** | Statique performant, élimine les problèmes CORS |
| Orchestration de tâches | **Apache Airflow** (Helm, LocalExecutor) | Standard pour DAGs, logs centralisés |
| Base métadonnées Airflow | **PostgreSQL 16** | Robuste, image officielle, déployée séparément du chart |
| Métriques | **Prometheus** (`kube-prometheus-stack`) | Scraping auto via ServiceMonitor |
| Dashboards | **Grafana** | Visualisation infra + métriques métier |

---

## Quickstart

### Prérequis

| Outil | Version | Rôle |
|---|---|---|
| [Docker Desktop](https://docs.docker.com/get-docker/) | ≥ 20.10 | Build des images + runtime kind |
| [kind](https://kind.sigs.k8s.io/) | ≥ 0.20 | Cluster Kubernetes local (dans Docker) |
| [kubectl](https://kubernetes.io/docs/tasks/tools/) | ≥ 1.28 | Client CLI Kubernetes |
| [Helm](https://helm.sh/) | ≥ 3.12 | Charts Airflow et kube-prometheus-stack |
| [GNU Make](https://www.gnu.org/software/make/) | ≥ 4.0 | Orchestration des commandes |

**Ressources Docker Desktop recommandées** : 4 CPU, 8 Go RAM (Settings → Resources).

Pour les commandes d'installation par OS (Windows / macOS / Linux) et le dépannage, voir [docs/PREREQUISITES.md](docs/PREREQUISITES.md).

### Déploiement en une commande

```bash
make all
```

Cette cible enchaîne : création du cluster kind → build des images dans Docker Desktop + chargement dans le cluster → déploiement de l'app NBA via Kustomize → installation de la stack monitoring (Helm) → installation d'Airflow avec son Postgres dédié. Compter 5 à 10 minutes au premier run.

### Cibles utiles

```bash
make help                    # Liste toutes les cibles disponibles
make status                  # État des 3 namespaces (nba, airflow, monitoring)

# Accès aux UIs
# Frontend NBA accessible directement (port mappé par kind) : http://localhost:30081
make port-forward-airflow    # Airflow UI     → http://localhost:8081 (admin/admin)
make port-forward-grafana    # Grafana        → http://localhost:3000 (admin/prom-operator)

# Observation
make logs-backend            # Logs streaming du backend FastAPI
make logs-airflow            # Logs streaming du scheduler Airflow

# Nettoyage
make destroy                 # Supprime Helm releases + namespaces (garde le cluster)
make cluster-down            # Supprime complètement le cluster kind
```

### Déploiement étape par étape

Si tu préfères contrôler chaque étape (debug, démo) :

```bash
make cluster-up        # 1. Crée le cluster kind (~30s)
make build             # 2. Build images dans Docker Desktop + charge dans kind
make nba               # 3. Déploie l'app NBA (Kustomize overlay dev)
make monitoring        # 4. Installe kube-prometheus-stack
make airflow           # 5. Installe Postgres dédié + Airflow (Helm)
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
├── k8s/                        # Manifestes Kubernetes (Kustomize)
│   ├── base/                   # Manifestes communs (Namespace, Deployments, Services, ServiceMonitor)
│   ├── overlays/
│   │   ├── dev/                # Overlay local (NodePort 30080/30081, imagePullPolicy: Never)
│   │   ├── staging/            # Stub pour pré-prod (HPA, Ingress, etc.)
│   │   └── prod/               # Stub pour prod managée (GKE/EKS/AKS)
│   ├── kind-config.yaml        # Configuration du cluster kind (port mapping inclus)
│   └── airflow-postgres.yaml   # Postgres dédié pour Airflow (hors Kustomize)
├── dags/                       # DAGs Airflow
│   └── nba_orchestration.py
├── airflow-values.yaml         # Values Helm pour Airflow
├── docs/
│   ├── PREREQUISITES.md        # Install des outils par OS + dépannage
│   ├── Rapport projet orchestra nba_predictor.pdf
│   └── *.jpg                   # Schémas d'architecture (Excalidraw exportés)
├── Makefile                    # Cibles d'orchestration (make help)
└── README.md                   # Ce fichier
```

---

## Points d'attention techniques

- **Workflow images avec kind** — `docker build` (dans Docker Desktop) puis `kind load docker-image` charge l'image dans le node containerd du cluster. Pas besoin de registry. La cible `make build` enchaîne les deux automatiquement.
- **`imagePullPolicy: Never`** — volontaire, car les images sont chargées localement dans le cluster (pas dans une registry).
- **Port mapping kind** — le cluster expose `localhost:30080` (backend) et `localhost:30081` (frontend) directement, sans port-forward.
- **Label `release: kube-prom`** — requis sur le ServiceMonitor pour que Prometheus le détecte.
- **PostgreSQL d'Airflow déployé séparément** — décision motivée par les instabilités du subchart Postgres du chart Airflow officiel (cf. rapport §6).
- **Secrets via Bitnami sealed-secrets (V4.1)** — password Postgres + URL SQLAlchemy Airflow chiffrés avec la clé publique du controller (committable dans `k8s/base/airflow-credentials-sealedsecret.yaml`, déchiffrement automatique côté cluster). Pour regénérer après rotation : `make seal-secrets` (nécessite `kubeseal` CLI, cf. [docs/PREREQUISITES.md](docs/PREREQUISITES.md)).

---

## Roadmap

Ce projet est en évolution active vers un vrai showcase Data Engineering. Prochaines étapes :

- [x] Kustomize base + overlays (dev / staging / prod)
- [x] Makefile pour automatiser le cycle complet (`make all`, `make destroy`, etc.)
- [x] CI/CD GitHub Actions (lint Ruff + Mypy strict, tests pytest, build Docker GHCR, scan Trivy warn-only, intégration K8s kind)
- [x] Tests unitaires (pytest) et d'intégration (kind)
- [x] Dockerfile multi-stage distroless + ré-activation Trivy `--exit-code 1` HIGH/CRITICAL avec `.trivyignore` documenté (Vague 4.2)
- [x] Secrets K8s via Bitnami sealed-secrets (password Postgres + URL SQLAlchemy Airflow chiffrés, controller dans `kube-system`) (Vague 4.1)
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
