# NBA Predictor — orchestration commands
#
# Usage : make <target>
# Prérequis : docker, kind, kubectl, helm, make — voir docs/PREREQUISITES.md
#
# Conventions :
#   - Toutes les cibles sont idempotentes (rejouables sans erreur)
#   - make help    affiche la liste des cibles avec leur description
#   - make all     déploie tout from scratch (cluster kind + images + nba + monitoring + airflow)

# --- Shell : sur Windows, forcer bash (Git Bash) au lieu de cmd.exe ---
# Raison : cmd.exe n'interprète ni les codes ANSI (\033[...) ni l'UTF-8 par
# défaut, ce qui casse les couleurs et les caractères accentués du help.
# Prérequis Windows : Git for Windows installé (C:\Program Files\Git\bin\bash.exe
# par défaut ; on tente aussi /usr/bin si environnement Git Bash actif).
#
# Note : certains ports Windows de Make (ezwinports notamment) ignorent SHELL
# si la valeur n'est pas un chemin absolu accessible. On utilise donc le
# chemin complet, avec espaces échappés par les guillemets.
ifeq ($(OS),Windows_NT)
SHELL := C:/Program Files/Git/bin/bash.exe
.SHELLFLAGS := -c
endif

# --- Variables (surchargables : make build BACKEND_TAG=2.0) ---
BACKEND_TAG  ?= 1.2
FRONTEND_TAG ?= 1.0
CLUSTER_NAME ?= nba-predictor
OVERLAY ?= dev

# Image node kind pinnée pour stabilité. Le tag par défaut de kind récent
# (kindest/node:v1.35.0) déclenche une incompatibilité kubeadm/API v1beta3
# qui fait timeout le kubelet (cf. kind#3994). On pin sur 1.32, dernière
# version éprouvée et compatible avec kind ≥ 0.27.
# Pour upgrader : tester d'abord avec `kind create cluster --image=...`
# et vérifier que le control-plane devient Ready.
KIND_NODE_IMAGE ?= kindest/node:v1.32.2@sha256:36187f6c542fa9b78d2d499de4c857249c5a0ac8cc2241bef2ccd92729a7a259

# Couleurs pour les messages
CYAN   := \033[36m
GREEN  := \033[32m
YELLOW := \033[33m
RESET  := \033[0m

.DEFAULT_GOAL := help
.PHONY: help all cluster-up cluster-down build deploy nba airflow monitoring sync-dags \
        sealed-secrets-install seal-secrets apply-sealed-secrets \
        port-forward-app port-forward-airflow port-forward-grafana \
        logs-backend logs-frontend logs-airflow status destroy clean-images

help: ## Affiche cette aide
	@printf "\n$(CYAN)NBA Predictor - Makefile$(RESET)\n\n"
	@printf "Usage : make $(YELLOW)<target>$(RESET)\n\n"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_-]+:.*?## / {printf "  $(YELLOW)%-22s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\n"

# =============================================================================
# Cycle complet
# =============================================================================

all: cluster-up build sealed-secrets-install monitoring deploy airflow ## Déploie tout from scratch (5-10 min)
	@printf "\n$(GREEN)[OK] Pipeline complet deploye.$(RESET)\n"
	@printf "  Frontend NBA accessible directement : http://localhost:30081\n"
	@printf "  Pour les UIs Airflow/Grafana : make port-forward-airflow | port-forward-grafana\n"

# =============================================================================
# Cluster kind (Kubernetes-in-Docker)
# =============================================================================

cluster-up: ## Crée le cluster kind 'nba-predictor' (1 control-plane + 1 worker)
	@if kind get clusters 2>/dev/null | grep -q "^$(CLUSTER_NAME)$$"; then \
		printf "$(GREEN)[OK] Cluster kind '$(CLUSTER_NAME)' deja existant.$(RESET)\n"; \
	else \
		printf "$(CYAN)> Creation du cluster kind '$(CLUSTER_NAME)' (image $(KIND_NODE_IMAGE))...$(RESET)\n"; \
		kind create cluster --config k8s/kind-config.yaml --image $(KIND_NODE_IMAGE) || { \
			printf "$(YELLOW)[!] Echec de creation du cluster. Voir messages ci-dessus.$(RESET)\n"; \
			exit 1; \
		}; \
		printf "$(GREEN)[OK] Cluster cree.$(RESET)\n"; \
	fi
	@kubectl cluster-info --context kind-$(CLUSTER_NAME)

cluster-down: ## Supprime complètement le cluster kind
	@printf "$(YELLOW)[!] Suppression du cluster kind '$(CLUSTER_NAME)'...$(RESET)\n"
	@kind delete cluster --name $(CLUSTER_NAME) 2>/dev/null || true
	@printf "$(GREEN)[OK] Cluster supprime.$(RESET)\n"

# =============================================================================
# Images Docker (build dans Docker Desktop, puis chargées dans le cluster kind)
# =============================================================================

build: ## Build les images backend/frontend et les charge dans le cluster kind
	@printf "$(CYAN)> Build des images dans Docker Desktop...$(RESET)\n"
	@docker build -t nba-backend:$(BACKEND_TAG) ./nba-api
	@docker build -t nba-frontend:$(FRONTEND_TAG) ./nba-web
	@printf "$(CYAN)> Chargement des images dans le cluster kind...$(RESET)\n"
	@kind load docker-image nba-backend:$(BACKEND_TAG) --name $(CLUSTER_NAME)
	@kind load docker-image nba-frontend:$(FRONTEND_TAG) --name $(CLUSTER_NAME)
	@printf "$(GREEN)[OK] Images construites et chargees : nba-backend:$(BACKEND_TAG), nba-frontend:$(FRONTEND_TAG)$(RESET)\n"

clean-images: ## Supprime les images NBA de Docker Desktop (le cluster garde sa copie)
	@docker rmi -f nba-backend:$(BACKEND_TAG) nba-frontend:$(FRONTEND_TAG) 2>/dev/null || true

# =============================================================================
# Application NBA (namespace nba)
# =============================================================================

deploy: nba ## Alias de make nba

nba: ## Déploie/met à jour l'app NBA via Kustomize (overlay = OVERLAY, défaut: dev)
	@printf "$(CYAN)> Deploiement de l'application NBA (overlay: $(OVERLAY))...$(RESET)\n"
	@kubectl apply -k k8s/overlays/$(OVERLAY)
	@printf "$(CYAN)> Attente que les pods soient Ready...$(RESET)\n"
	@kubectl wait --for=condition=Ready pod -l app=nba-backend -n nba --timeout=120s
	@kubectl wait --for=condition=Ready pod -l app=nba-frontend -n nba --timeout=60s
	@printf "$(GREEN)[OK] Application NBA deployee et prete.$(RESET)\n"

# =============================================================================
# Monitoring (Prometheus + Grafana via Helm)
# =============================================================================

monitoring: ## Déploie kube-prometheus-stack (Prometheus + Grafana) via Helm + ServiceMonitor NBA
	@printf "$(CYAN)> Installation/upgrade de kube-prometheus-stack...$(RESET)\n"
	@helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
	@helm repo update >/dev/null
	@helm upgrade --install kube-prom prometheus-community/kube-prometheus-stack \
		--namespace monitoring --create-namespace \
		--wait --timeout 5m
	@printf "$(CYAN)> Application du ServiceMonitor pour le backend NBA...$(RESET)\n"
	@kubectl apply -f k8s/base/backend-servicemonitor.yaml
	@printf "$(GREEN)[OK] Stack monitoring deployee + ServiceMonitor NBA actif.$(RESET)\n"
	@printf "  Grafana : admin / prom-operator (voir kubectl get secret -n monitoring kube-prom-grafana)\n"

# =============================================================================
# Secrets (sealed-secrets controller + chiffrement des Secrets airflow/postgres)
# =============================================================================

sealed-secrets-install: ## Installe le controller Bitnami sealed-secrets (kube-system)
	@printf "$(CYAN)> Installation du controller sealed-secrets...$(RESET)\n"
	@helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets >/dev/null 2>&1 || true
	@helm repo update sealed-secrets >/dev/null
	@helm upgrade --install sealed-secrets sealed-secrets/sealed-secrets \
		--namespace kube-system \
		--set fullnameOverride=sealed-secrets-controller \
		--wait --timeout 3m
	@printf "$(GREEN)[OK] Controller sealed-secrets installe (kube-system).$(RESET)\n"

seal-secrets: ## Genere les SealedSecret depuis k8s/secrets/*.unsealed.yaml (necessite kubeseal CLI)
	@command -v kubeseal >/dev/null 2>&1 || { \
		printf "$(YELLOW)[!] kubeseal CLI non trouve. Installer via :$(RESET)\n"; \
		printf "    Windows : scoop install kubeseal  OU  https://github.com/bitnami-labs/sealed-secrets/releases\n"; \
		printf "    macOS   : brew install kubeseal\n"; \
		printf "    Linux   : voir https://github.com/bitnami-labs/sealed-secrets#installation\n"; \
		exit 1; \
	}
	@printf "$(CYAN)> Scellement des Secrets...$(RESET)\n"
	@kubeseal --controller-namespace=kube-system \
		--controller-name=sealed-secrets-controller \
		--format=yaml \
		< k8s/secrets/airflow-credentials.unsealed.yaml \
		> k8s/base/airflow-credentials-sealedsecret.yaml
	@printf "$(GREEN)[OK] SealedSecret genere : k8s/base/airflow-credentials-sealedsecret.yaml$(RESET)\n"
	@printf "  Verifier le diff puis 'git add k8s/base/airflow-credentials-sealedsecret.yaml'\n"

apply-sealed-secrets: ## Applique les SealedSecret committes (controller deja installe requis)
	@printf "$(CYAN)> Application des SealedSecret committes...$(RESET)\n"
	@kubectl get namespace airflow >/dev/null 2>&1 || kubectl create namespace airflow
	@kubectl apply -f k8s/base/airflow-credentials-sealedsecret.yaml
	@printf "$(CYAN)> Attente du dechiffrement par le controller...$(RESET)\n"
	@for secret in airflow-postgres-secret airflow-metadata-secret airflow-admin-secret; do \
		for i in $$(seq 1 30); do \
			if kubectl get secret $$secret -n airflow >/dev/null 2>&1; then \
				printf "$(GREEN)  [OK] $$secret dechiffre$(RESET)\n"; break; \
			fi; \
			sleep 1; \
		done; \
	done

# =============================================================================
# Airflow (Postgres dédié + Helm chart officiel)
# =============================================================================

airflow: apply-sealed-secrets ## Déploie Postgres dédié puis Airflow (Helm) avec attente Ready
	@printf "$(CYAN)> Creation du namespace airflow si necessaire...$(RESET)\n"
	@kubectl get namespace airflow >/dev/null 2>&1 || kubectl create namespace airflow
	@printf "$(CYAN)> Deploiement de PostgreSQL dedie a Airflow...$(RESET)\n"
	@kubectl apply -f k8s/airflow-postgres.yaml
	@kubectl wait --for=condition=Ready pod -l app=airflow-postgres -n airflow --timeout=120s
	@printf "$(GREEN)[OK] Postgres pret.$(RESET)\n"
	@printf "$(CYAN)> Installation/upgrade d'Airflow via Helm...$(RESET)\n"
	@helm repo add apache-airflow https://airflow.apache.org >/dev/null 2>&1 || true
	@helm repo update >/dev/null
	# Pas de --wait : le chart Airflow utilise un hook post-install pour le
	# Job de migration DB, et --wait crée un deadlock (les pods attendent
	# les migrations, le hook attend que les pods soient Ready). On laisse
	# Helm sortir dès que les manifestes sont apply, puis on attend
	# explicitement le Job de migration et les pods principaux.
	@helm upgrade --install airflow apache-airflow/airflow \
		--namespace airflow -f airflow-values.yaml \
		--timeout 10m
	@printf "$(CYAN)> Attente que les pods Airflow soient Ready (migration DB + demarrage, ~5 min au premier run)...$(RESET)\n"
	@kubectl wait --for=condition=Ready pod -l component=api-server -n airflow --timeout=10m
	@kubectl wait --for=condition=Ready pod -l component=scheduler -n airflow --timeout=5m
	@$(MAKE) --no-print-directory sync-dags
	@printf "$(GREEN)[OK] Airflow deploye.$(RESET)\n"
	@printf "  UI : admin/admin - make port-forward-airflow puis http://localhost:8081\n"

sync-dags: ## Synchronise dags/ local vers le PVC Airflow (via kubectl cp dans le scheduler)
	@printf "$(CYAN)> Synchronisation des DAGs vers le cluster...$(RESET)\n"
	@for dag in dags/*.py; do \
		printf "    - $$dag\n"; \
		kubectl cp -n airflow -c scheduler "$$dag" airflow-scheduler-0:/opt/airflow/dags/$$(basename $$dag); \
	done
	@printf "$(GREEN)[OK] DAGs synchronises. Le dag-processor les detectera dans ~30s.$(RESET)\n"

# =============================================================================
# Port-forward (à lancer dans des terminaux séparés)
# =============================================================================

port-forward-app: ## Expose le frontend NBA sur http://localhost:8080
	@printf "$(CYAN)> Frontend NBA : http://localhost:8080$(RESET)  (Ctrl+C pour arreter)\n"
	@kubectl port-forward -n nba svc/nba-frontend-svc 8080:80

port-forward-airflow: ## Expose l'UI Airflow sur http://localhost:8081
	@printf "$(CYAN)> Airflow UI : http://localhost:8081 (admin/admin)$(RESET)  (Ctrl+C pour arreter)\n"
	@kubectl port-forward -n airflow svc/airflow-api-server 8081:8080

port-forward-grafana: ## Expose Grafana sur http://localhost:3000
	@printf "$(CYAN)> Grafana : http://localhost:3000 (admin/prom-operator)$(RESET)  (Ctrl+C pour arreter)\n"
	@kubectl port-forward -n monitoring svc/kube-prom-grafana 3000:80

# =============================================================================
# Observation
# =============================================================================

status: ## Affiche l'état des 3 namespaces
	@printf "$(CYAN)Namespace nba$(RESET)\n"
	@kubectl get pods,svc -n nba 2>&1 || true
	@if kubectl api-resources --api-group=monitoring.coreos.com 2>/dev/null | grep -q ServiceMonitor; then \
		kubectl get servicemonitor -n monitoring -l release=kube-prom 2>&1 || true; \
	else \
		printf "  (ServiceMonitor CRD pas encore installe -- lancer 'make monitoring')\n"; \
	fi
	@printf "\n$(CYAN)Namespace airflow$(RESET)\n"
	@kubectl get pods,svc -n airflow 2>&1 || true
	@printf "\n$(CYAN)Namespace monitoring$(RESET)\n"
	@kubectl get pods,svc -n monitoring 2>&1 || true

logs-backend: ## Logs en streaming du backend NBA
	@kubectl logs -f -n nba -l app=nba-backend --tail=100

logs-frontend: ## Logs en streaming du frontend NBA
	@kubectl logs -f -n nba -l app=nba-frontend --tail=100

logs-airflow: ## Logs en streaming du scheduler Airflow
	@kubectl logs -f -n airflow -l component=scheduler --tail=100

# =============================================================================
# Nettoyage
# =============================================================================

destroy: ## Supprime les workloads (Helm releases + namespaces) — garde le cluster
	@printf "$(YELLOW)[!] Suppression des workloads...$(RESET)\n"
	@helm uninstall -n airflow airflow 2>/dev/null || true
	@helm uninstall -n monitoring kube-prom 2>/dev/null || true
	@kubectl delete -k k8s/overlays/$(OVERLAY) --ignore-not-found
	@kubectl delete namespace airflow --ignore-not-found
	@kubectl delete namespace monitoring --ignore-not-found
	@kubectl delete namespace nba --ignore-not-found
	@printf "$(GREEN)[OK] Workloads supprimes. Pour supprimer le cluster : make cluster-down.$(RESET)\n"
