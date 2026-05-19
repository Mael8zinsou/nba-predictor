# NBA Predictor — MLOps Pipeline

> Industrialisation cloud-native d'une application ML de classification NBA : conteneurisation, orchestration Kubernetes, automatisation Airflow, observabilité Prometheus/Grafana, sécurité réseau et secrets. Déployable en local sur un cluster [kind](https://kind.sigs.k8s.io/) en une commande.

![Kubernetes](https://img.shields.io/badge/Kubernetes-1.32-326CE5?logo=kubernetes&logoColor=white)
![Calico](https://img.shields.io/badge/Calico-CNI-FF6900?logo=tigera&logoColor=white)
![Airflow](https://img.shields.io/badge/Apache_Airflow-3.x-017CEE?logo=apacheairflow&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Prometheus](https://img.shields.io/badge/Prometheus-monitoring-E6522C?logo=prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-dashboards-F46800?logo=grafana&logoColor=white)
![Distroless](https://img.shields.io/badge/Docker-distroless-2496ED?logo=docker&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## Pourquoi ce projet

Une application Machine Learning fonctionnelle (modèle entraîné + API + frontend) ne suffit pas pour la production. Ce projet répond à plusieurs questions concrètes d'industrialisation :

- **Conteneurisation** — image distroless, securityContext strict, scan Trivy bloquant
- **Orchestration** — Kubernetes via kind, Kustomize, Helm pour les charts upstream
- **Sécurité** — Secrets via sealed-secrets, NetworkPolicies zero-trust avec Calico
- **Observabilité** — métriques métier + infra, scrape automatique via ServiceMonitor
- **Automatisation** — DAGs Airflow, CI/CD GitHub Actions, Dependabot

Le résultat : un pipeline reproductible, observable, sécurisé et démontrable, représentatif des solutions production.

> **Crédit** — l'application NBA initiale (modèle, API, frontend) est l'œuvre de **Ketsia MULAPI** (juin 2021). La partie industrialisation a été conçue par **Maël M. ZINSOU** en 2026 dans le cadre du cours "Infrastructures et orchestration de données" (YNOV).

---

## Architecture

3 namespaces Kubernetes isolés sur un cluster local [kind](https://kind.sigs.k8s.io/) avec CNI Calico :

| Namespace | Composants | Rôle |
|---|---|---|
| `nba` | Frontend Nginx + Backend FastAPI (distroless) | Application métier |
| `airflow` | Apache Airflow 3 (Helm) + PostgreSQL 16 dédié | Orchestration des appels API |
| `monitoring` | kube-prometheus-stack (Prometheus + Grafana) | Supervision via ServiceMonitor |

![Architecture globale](docs/architecture_excalidraw.jpg)

**Flux principaux** :
- **Applicatif** : navigateur → Nginx (NodePort 30081, reverse proxy `/api/*`) → FastAPI
- **Orchestration** : DAG `nba_orchestration` → `GET /api/nba/predict` (cross-namespace autorisé)
- **Observabilité** : FastAPI `/metrics` → Prometheus → Grafana

**Sécurité (Vague 4)** :
- Image backend en `gcr.io/distroless/python3-debian12:nonroot` (~10 CVE HIGH résiduelles documentées dans `.trivyignore` vs ~250 sur l'image slim)
- Secrets Postgres/Airflow chiffrés via [Bitnami sealed-secrets](https://github.com/bitnami-labs/sealed-secrets) (committable)
- NetworkPolicies zero-trust : pod intrus dans `default` → backend ou postgres = **timeout effectif**

> Détails techniques complets → [docs/doc.md](docs/doc.md).

---

## Quickstart

### Prérequis

| Outil | Version | Rôle |
|---|---|---|
| [Docker Desktop](https://docs.docker.com/get-docker/) | ≥ 20.10 | Build des images + runtime kind |
| [kind](https://kind.sigs.k8s.io/) | ≥ 0.27 | Cluster Kubernetes local |
| [kubectl](https://kubernetes.io/docs/tasks/tools/) | ≥ 1.28 | Client CLI Kubernetes |
| [Helm](https://helm.sh/) | ≥ 3.12 | Charts Airflow + kube-prometheus-stack + sealed-secrets |
| [GNU Make](https://www.gnu.org/software/make/) | ≥ 4.0 | Orchestration des commandes |
| [kubeseal](https://github.com/bitnami-labs/sealed-secrets) | ≥ 0.27 | Regénération des SealedSecret (optionnel) |

**Ressources Docker Desktop** : 4 CPU, 8 Go RAM minimum.
**Installation par OS** → [docs/PREREQUISITES.md](docs/PREREQUISITES.md).

### Déploiement en une commande

```bash
make all
```

Enchaîne : cluster kind + Calico CNI → build images + chargement kind → sealed-secrets controller → app NBA (Kustomize + NetworkPolicies) → monitoring stack (Helm) → Airflow + Postgres dédié. ~5-10 min au premier run.

### Accès aux UIs

```bash
# Frontend NBA + API via Ingress (V4.5)
open http://nba.localhost
# Pré-requis : ajouter '127.0.0.1 nba.localhost' à /etc/hosts (Linux/macOS)
# ou C:\Windows\System32\drivers\etc\hosts (Windows). Sur systemd-resolved
# récent, *.localhost résout automatiquement.

# Airflow + Grafana (port-forward)
make port-forward-airflow    # http://localhost:8081 (admin/admin)
make port-forward-grafana    # http://localhost:3000 (admin/prom-operator)

# Démo HPA scale-up sous charge (V4.4)
make load-test               # 50 workers x 60s, observer : kubectl get hpa -n nba -w
```

### Cibles utiles

```bash
make help                # liste toutes les cibles disponibles
make status              # état des 3 namespaces
make logs-backend        # streaming des logs backend
make destroy             # supprime workloads (garde le cluster)
make cluster-down        # supprime le cluster kind
```

> Cookbook complet des commandes par vague → [docs/key_commands.md](docs/key_commands.md).

---

## Roadmap

- [x] Portfolio fundamentals (README, LICENSE, CONTRIBUTING) **— Vague 1**
- [x] Developer experience (Makefile, Kustomize overlays dev/staging/prod) **— Vague 2**
- [x] Migration Minikube → kind **— Vague 2bis**
- [x] CI/CD GitHub Actions (5 jobs lint+test, build Docker GHCR, k8s integration) **— Vague 3**
- [x] Tests unitaires (pytest) et d'intégration (FastAPI TestClient + kind smoke) **— Vague 3**
- [x] Secrets K8s via Bitnami sealed-secrets (Postgres + URL SQLAlchemy chiffrés) **— Vague 4.1**
- [x] Dockerfile multi-stage distroless + Trivy `--exit-code 1` + securityContext strict **— Vague 4.2**
- [x] NetworkPolicies zero-trust + CNI Calico via tigera-operator **— Vague 4.3**
- [x] HorizontalPodAutoscaler backend (CPU 70%, min 2 max 5) + metrics-server + load test **— Vague 4.4**
- [x] Ingress nginx (`nba.localhost`) + PodDisruptionBudgets backend/frontend **— Vague 4.5**
- [ ] Observabilité avancée : Grafana dashboards versionnés, Alertmanager, Loki **— Vague 5**
- [ ] Pipeline d'entraînement reproductible (MLflow + DVC + fix bug `preprocess()`) **— Vague 6**
- [ ] Présentation portfolio : Medium article, ADR, demo vidéo, GitHub Pages **— Vague 7**

---

## Documentation

| Document | Audience | Quoi |
|---|---|---|
| [README.md](README.md) (ce fichier) | Visiteur, recruteur | Pitch, archi, quickstart, roadmap |
| [docs/doc.md](docs/doc.md) | Ingénieur, contributeur | Référence technique profonde : pourquoi des choix, débogage, ADR |
| [docs/key_commands.md](docs/key_commands.md) | Toi, futur dev | Cookbook chronologique : commandes exactes par vague |
| [docs/PREREQUISITES.md](docs/PREREQUISITES.md) | Tout le monde | Install des outils par OS (Windows / macOS / Linux) |
| [docs/Rapport projet orchestra nba_predictor.pdf](docs/Rapport%20projet%20orchestra%20nba_predictor.pdf) | Jury / lecteur académique | Rapport rendu pour le cours (V3) |

---

## License

[MIT](LICENSE).

Le code applicatif initial est © Ketsia MULAPI 2021. L'industrialisation est © Maël M. ZINSOU 2026.

---

## Contact

Maël M. ZINSOU — [maelzinsou@proton.me](mailto:maelzinsou@proton.me)
