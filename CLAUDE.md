# NBA Predictor — Orchestration & Infrastructure

Projet d'industrialisation d'une application ML de classification de joueurs NBA (cours "Infrastructures et orchestration de données", YNOV, Ketsia Mulapi Tita). Auteur de la partie orchestration/infra : Maël M. ZINSOU. Le code applicatif original (API + frontend) est de Ketsia Mulapi ; le rapport de référence est [docs/Rapport projet orchestra nba_predictor.pdf](docs/Rapport projet orchestra nba_predictor.pdf).

L'objectif n'est pas le modèle ML (régression logistique simple, déjà entraînée et sérialisée dans `classifier.pikl`), mais le **pipeline d'industrialisation** : conteneurisation, orchestration Kubernetes, automatisation Airflow, observabilité Prometheus/Grafana.

## Stack & architecture

Déploiement local via **kind** (Kubernetes-in-Docker), organisé en 3 namespaces Kubernetes. Le cluster tourne dans des conteneurs Docker visibles dans Docker Desktop (1 control-plane + 1 worker, cf. [k8s/kind-config.yaml](k8s/kind-config.yaml)).

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
- [k8s/](k8s/) — manifestes Kubernetes en **Kustomize** : `base/` (Namespace, Deployments, Services, ServiceMonitor) + `overlays/dev` (`imagePullPolicy: Never`, NodePorts 30080/30081), `overlays/staging` et `overlays/prod` en stubs. `kind-config.yaml` à la racine de `k8s/` (config du cluster local : 1 control-plane + 1 worker, port mapping pour exposer 30080/30081 sur localhost). `airflow-postgres.yaml` reste à la racine de `k8s/` (bootstrap d'Airflow, pas dans le scope de l'app NBA).
- [dags/](dags/) — DAGs Airflow (`nba_orchestration.py`).
- [airflow-values.yaml](airflow-values.yaml) — values Helm pour Airflow (LocalExecutor, Postgres externe, persistance DAGs + logs).
- [docs/](docs/) — rapport PDF + schémas Excalidraw (architecture et flux) + [PREREQUISITES.md](docs/PREREQUISITES.md) (install outils par OS).
- [Makefile](Makefile) — cibles d'orchestration. `make help` pour la liste. Cibles principales : `make all` (déploiement complet), `make cluster-up`/`cluster-down` (gestion cluster kind), `make build` (Docker Desktop + `kind load`), `make nba|airflow|monitoring`, `make port-forward-*`, `make status`, `make destroy`. Toutes les cibles sont idempotentes. Sur Windows, le Makefile force `SHELL := bash.exe` (Git Bash) — voir l'en-tête du fichier.
- [tests/](tests/) — suite pytest : `test_predictor.py` (17 tests unit sur NBAPredictor, dont 1 xfail strict documentant le bug `preprocess()` Min-Max — fix V6), `test_api.py` (15 tests d'intégration FastAPI via TestClient). `conftest.py` bascule le cwd sur `nba-api/` pour les chemins relatifs et insère `nba-api/` dans `sys.path`.
- [pyproject.toml](pyproject.toml) — config Ruff (lint + format), Mypy (strict), Pytest. Ignore les codes NBA (TOV, FGM, REB...) en majuscules dans les noms d'arguments (`N803`, `N806`). Filterwarnings ignore `InconsistentVersionWarning` de sklearn (modèle 0.24.1 vs runtime 1.5.1, fix V6).
- [requirements-dev.txt](requirements-dev.txt) — dépendances dev/CI/test (ruff, mypy, pytest, pytest-cov, httpx, pre-commit, types-requests, detect-secrets).
- [.pre-commit-config.yaml](.pre-commit-config.yaml) — hooks pre-commit alignés CI : trailing-whitespace, end-of-file-fixer, check-yaml/json/toml, ruff (+fix), ruff-format, yamllint, hadolint, detect-secrets.
- [.secrets.baseline](.secrets.baseline) — baseline detect-secrets : ne contient que des hashes (jamais les secrets en clair). Faux positifs marqués : password `admin/admin` Airflow, hashes Bootstrap minifié.
- [.github/workflows/](.github/workflows/) — 3 workflows GitHub Actions :
  - `ci.yml` : 5 jobs parallèles (python-lint, python-test, yaml-lint, k8s-validate, docker-lint hadolint)
  - `docker.yml` : build des 2 images + scan Trivy (warn-only) + upload SARIF GitHub Security + push GHCR (`ghcr.io/mael8zinsou/nba-{backend,frontend}:main|sha-...`)
  - `k8s-integration.yml` : cluster kind dans CI + apply Kustomize + 3 smoke tests curl. Workaround `kind load image-archive` via tarball pour éviter le bug containerd snapshotter du runner.
- [.github/dependabot.yml](.github/dependabot.yml) — MAJ hebdo (lundi 8h Paris) pip × 2, docker × 2, github-actions. Groupé par patch/minor (cf. configuration majors ci-dessous).

## Conventions et points d'attention

- **Workflow images avec kind** : `docker build` dans Docker Desktop, puis `kind load docker-image <tag> --name nba-predictor` pour charger dans le node containerd du cluster. Pas de registry. `imagePullPolicy: Never` est appliqué par patch Kustomize dans [k8s/overlays/dev/image-pull-policy-never.yaml](k8s/overlays/dev/image-pull-policy-never.yaml) pour éviter tout pull. La cible `make build` enchaîne build + load automatiquement.
- **Tags d'image en dur** : `nba-backend:1.2` (V4.2 distroless) et `nba-frontend:1.0` (dans `k8s/base/*-deployment.yaml`). Si rebuild, surchargeables via `make build BACKEND_TAG=2.0`, mais penser à bumper les tags dans les manifestes ET dans `.github/workflows/k8s-integration.yml`.
- **Kustomize, pas Helm pour l'app NBA** : on utilise `kubectl kustomize k8s/overlays/dev | kubectl apply -f -` (ce que fait `make nba`). Helm n'est utilisé que pour les charts upstream (Airflow, kube-prometheus-stack). Décision motivée par la simplicité de l'app NBA — un chart Helm maison serait surdimensionné.
- **CORS volontairement géré côté Nginx** (pas dans FastAPI en prod) : le frontend doit toujours appeler des chemins relatifs `/api/*`, jamais `localhost:8080`.
- **ServiceMonitor → label `release: kube-prom` obligatoire** : sans ce label, Prometheus ne scrape pas (cf. section 6 du rapport, problème rencontré et résolu).
- **PostgreSQL d'Airflow déployé séparément** (pas le subchart) : décision motivée par les instabilités du chart Airflow officiel sur le subchart Postgres + PVC.
- **Secrets via Bitnami sealed-secrets (V4.1)** : password Postgres + URL SQLAlchemy Airflow ne sont plus en dur. Le pattern :
  - **Source en clair** dans `k8s/secrets/airflow-credentials.unsealed.yaml` (gitignored via `*.unsealed.yaml`)
  - **`kubeseal` chiffre** avec la clé publique du controller → `k8s/base/airflow-credentials-sealedsecret.yaml` (committable, illisible sans la master key du controller)
  - **Controller dans `kube-system`** déchiffre côté cluster → 3 Secret K8s standards (`airflow-postgres-secret`, `airflow-metadata-secret`, `airflow-admin-secret`)
  - **Consommation** : postgres via `envFrom: secretRef`, chart Airflow via `data.metadataSecretName`
  - **Cibles Makefile** : `make sealed-secrets-install` (controller), `make seal-secrets` (regen), `make apply-sealed-secrets` (auto via `make airflow`)
  - **Limite connue** : le password admin UI Airflow (`webserver.defaultUser.password`) reste en clair dans `airflow-values.yaml` car le chart ne supporte pas un Secret pour ce champ. Le SealedSecret `airflow-admin-secret` existe en prévision d'un V4.1bis (customisation `createUserJob.command`).
  - **Backup master key** : si on perd la clé du controller, tous les SealedSecret deviennent inutilisables. Sauvegarder via `kubectl get secret -n kube-system -l sealedsecrets.bitnami.com/sealed-secrets-key -o yaml > sealed-secrets-master.key` (à stocker offline).
- **Métriques Prometheus exposées dans [nba-api/app.py](nba-api/app.py)** : `nba_api_requests_total` (Counter) et `nba_api_request_latency_seconds` (Histogram), via `/metrics`. C'est l'une des deux modifications principales du code source initial (l'autre étant le passage du frontend en chemins relatifs).
- **Accès local via port mapping kind** : depuis V4.3, seul le frontend est exposé en NodePort `localhost:30081`. Le backend est en ClusterIP, accessible uniquement via le reverse-proxy nginx (`/api/*` → `nba-backend-svc:8080`). Airflow UI et Grafana restent accessibles via `make port-forward-airflow` / `make port-forward-grafana`.
- **CNI Calico (V4.3)** : kindnet (CNI par défaut de kind) ne supporte pas les NetworkPolicies. On désactive kindnet dans `k8s/kind-config.yaml` (`networking.disableDefaultCNI: true`) et `make cluster-up` enchaîne automatiquement avec `calico-install` via le tigera-operator (`k8s/calico-installation.yaml`). Sans Calico, les nodes restent `NotReady`.
- **NetworkPolicies (V4.3)** : pattern zero-trust (default-deny + allow-list). Les 3 namespaces sont isolés :
  - `nba` : default-deny ingress + frontend ouvert (NodePort) + backend ouvert uniquement depuis (frontend / `role=monitoring` / `role=orchestration`)
  - `airflow` : default-deny + allow-intra-namespace (graphe interne complexe) + api-server accessible en port-forward + statsd scrapable depuis `role=monitoring`
  - `monitoring` : default-deny + allow-intra-namespace + Grafana/Prometheus UIs accessibles en port-forward
  - Cross-namespace : namespaces labellés `role=app|orchestration|monitoring` (label posé par les cibles Makefile `nba`/`airflow`/`monitoring`)
  - Manifests : `k8s/base/networkpolicies-{nba,airflow,monitoring}.yaml`. Le fichier nba est dans Kustomize (overlay dev), les autres sont appliqués séparément par les cibles `make airflow` et `make monitoring`.
  - Egress non filtré pour ce projet (cf. commentaires dans les manifests). Resserrer = V4.3bis.
- **Le modèle ML est figé en V3** : `classifier.pikl` est un artefact pré-entraîné (sklearn 0.24.1, vieille version), pas encore de pipeline d'entraînement dans ce repo. **Bug connu** documenté en xfail strict : `preprocess()` calcule min/max sur le vecteur unique au lieu d'utiliser les stats du dataset (voir `memory/project_known_bugs.md`). Fix prévu en Vague 6 avec MLflow + scaler sérialisé.
- **Backend en image distroless (V4.2)** : `nba-api/Dockerfile` est multi-stage — builder `python:3.11-slim` qui installe les deps dans `/install` (prefix), puis runtime `gcr.io/distroless/python3-debian12:nonroot` qui copie `/install` et utilise son Python natif via `PYTHONPATH=/install/lib/python3.11/site-packages`. UID 65532, pas de shell, pas d'apt. Le Deployment K8s a un `securityContext` strict (`runAsNonRoot`, `readOnlyRootFilesystem`, `drop ALL caps`). Python passé 3.10 → 3.11 (cohérence builder/runtime), le pickle sklearn 0.24.1 reste chargeable.
- **Trivy en mode bloquant (V4.2)** : `--exit-code 1` actif dans `.github/workflows/docker.yml`, avec `.trivyignore` racine qui liste explicitement les CVE acceptées (CVE OS distroless impatchables côté projet + 1 starlette nécessitant fastapi ≥0.117). Chaque ignore a une `Revisit by:` date pour audit trimestriel. Le scan SARIF reste actif pour GitHub Security.
- **Trivy installé directement via apt** (`apt-get install trivy` depuis le dépôt officiel Aqua) plutôt que via `aquasecurity/trivy-action` : 4 problèmes consécutifs avec l'action (versions inexistantes, deps `setup-trivy@v0.2.2` non publiée, `install.sh exit 1`). Pilotage direct = stable et auditable.
- **GHCR + Code Scanning nécessitent un repo public** : `ghcr.io/mael8zinsou/nba-*` et l'onglet Security sont gratuits uniquement pour les repos publics. Sur un repo privé, Code Scanning exige GitHub Advanced Security ($49/user/mois). Le repo nba-predictor reste donc public.
- **Permission `actions: read` requise pour upload SARIF** : `codeql-action/upload-sarif@v3` a besoin de `actions: read` en plus de `security-events: write` pour récupérer les métadonnées du run. Documenté dans le README de codeql-action mais facile à manquer.

## Environnement de dev

- Plateforme principale : **Windows + PowerShell** (utiliser la syntaxe PowerShell pour les commandes). Le cluster Kubernetes tourne via `kind` dans Docker Desktop. Le Makefile force `SHELL := C:/Program Files/Git/bin/bash.exe` sur Windows car `ezwinports.make` ne respecte pas `SHELL` avec un chemin relatif et `cmd.exe` ne gère pas les codes ANSI / UTF-8.
- Python 3.10 pour la CI et le dev local (`requirements-dev.txt`), **Python 3.11 dans le backend distroless** (cf. [nba-api/Dockerfile](nba-api/Dockerfile)).
- Pour tester l'API en local hors K8s : `cd nba-api ; uvicorn app:app --reload --port 8080` puis ouvrir `http://localhost:8080/docs`.

## Workflow de développement

- **Pre-commit hooks installés** : `pre-commit install` à la racine. Toute modif passe par ruff, ruff-format, yamllint, hadolint, detect-secrets avant `git commit`.
- **Tests locaux** : `pytest` depuis la racine (32 tests, 1 xfailed attendu, ~3s). `pytest --cov=nba-api` pour la coverage.
- **Lint manuel** : `ruff check . && ruff format --check . && mypy nba-api dags`.
- **Avant chaque push** : vérifier `pytest` + `ruff` localement, sinon la CI fail.

## Ce que je ne dois PAS faire sans confirmation

- Toucher au modèle `classifier.pikl` ou au dataset `nba_logreg.csv` hors du contexte Vague 6 (pipeline d'entraînement MLflow).
- "Corriger" `preprocess()` au passage : le fix doit venir avec son scaler sérialisé en V6, sinon on casse les prédictions sans pouvoir re-générer le modèle. Le xfail strict du test `test_single_vector_uses_dataset_statistics` est le rappel.
- Modifier `.trivyignore` sans ajouter de date `Revisit by:` — chaque ignore doit avoir une échéance d'audit pour éviter d'accumuler de la dette CVE silencieuse.
- Supprimer les `__pycache__/` ou autres caches versionnés — vérifier d'abord ce qui est effectivement utile.

Note : le code applicatif de Ketsia (`functions.py`, frontend) est librement refactorable depuis le 2026-05-16 (cf. `memory/feedback_app_code_refactor_allowed.md`).
