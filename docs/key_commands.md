# Commandes clés et manipulations — journal chronologique

> Cookbook référence : pour chaque vague, les commandes exactes exécutées + le contexte décisionnel.
> Sert de mémoire pour rejouer une étape, débugger, ou onboarder un futur dev.
> Pour la doc technique → [doc.md](doc.md). Pour le quickstart → [README.md](../README.md).

---

## Table des matières

- [Setup initial](#setup-initial)
- [Cycle de vie complet (make all)](#cycle-de-vie-complet-make-all)
- [Vague 1 — Portfolio fundamentals](#vague-1--portfolio-fundamentals)
- [Vague 2 — Developer Experience](#vague-2--developer-experience)
- [Vague 2bis — Migration Minikube → kind](#vague-2bis--migration-minikube--kind)
- [Vague 3 — CI/CD GitHub Actions](#vague-3--cicd-github-actions)
- [Vague 4.1 — SealedSecrets](#vague-41--sealedsecrets)
- [Vague 4.2 — Dockerfile distroless + Trivy bloquant](#vague-42--dockerfile-distroless--trivy-bloquant)
- [Vague 4.3 — NetworkPolicies + Calico](#vague-43--networkpolicies--calico)
- [Vague 4.4 — HPA + metrics-server](#vague-44--hpa--metrics-server)
- [Vague 4.5 — Ingress + PDB](#vague-45--ingress--pdb)
- [Vague 5 — Dashboard + Alerting](#vague-5--dashboard--alerting)
- [Opérations quotidiennes](#opérations-quotidiennes)
- [Dépannage](#dépannage)

---

## Setup initial

### Vérifier que les outils sont installés

```bash
docker --version       # Docker Desktop ≥ 20.10
kind --version         # ≥ 0.27 (compatible kubeadm K8s 1.32)
kubectl version --client
helm version --short
make --version         # ≥ 4.0
kubeseal --version     # Pour V4.1+ (regénération SealedSecret)
```

Install par OS → [PREREQUISITES.md](PREREQUISITES.md).

### Vérifier que Docker Desktop est démarré

```powershell
docker info
# Doit afficher 'Server Version: XX.X.X' (pas 'Cannot connect to the Docker daemon')
```

> **Important Windows** : démarrer Docker Desktop **avant** la première commande `make` (sinon `kind create cluster` échoue : pas de daemon).

### Cloner le repo et installer les pre-commit hooks

```bash
git clone https://github.com/Mael8zinsou/nba-predictor.git
cd nba-predictor
pip install -r requirements-dev.txt
pre-commit install
```

---

## Cycle de vie complet (`make all`)

La cible `make all` enchaîne **tout** le pipeline. ~5-10 min au premier run, ~2-3 min les fois suivantes (cache Docker + helm).

```bash
make all
```

**Ordre exact** (cf. Makefile) :

```
all:
  ├── cluster-up                # 1. Crée cluster kind + installe Calico (~1 min)
  ├── build                     # 2. docker build × 2 + kind load × 2 (~2 min cache cold)
  ├── sealed-secrets-install    # 3. Helm install controller dans kube-system (~30s)
  ├── monitoring                # 4. Helm install kube-prom-stack + ServiceMonitor + NP (~2 min)
  ├── deploy (alias de nba)     # 5. kubectl apply -k overlays/dev + wait pods Ready
  └── airflow                   # 6. SealedSecrets + postgres + Helm install Airflow + NP (~4 min)
```

À la fin :
- Frontend NBA : `http://localhost:30081`
- API NBA via reverse-proxy : `http://localhost:30081/api/nba/predict?...`
- Airflow UI : `make port-forward-airflow` → `http://localhost:8081` (admin/admin)
- Grafana : `make port-forward-grafana` → `http://localhost:3000` (admin/prom-operator)

### Tear down complet

```bash
make destroy       # supprime workloads (Helm releases + namespaces), garde le cluster
make cluster-down  # supprime le cluster kind
```

---

## Vague 1 — Portfolio fundamentals

### Init repo GitHub + License + .gitignore

```bash
git init
git add LICENSE README.md .gitignore
git commit -m "feat: initial public release — NBA Predictor MLOps pipeline"
gh repo create Mael8zinsou/nba-predictor --public --source=.  --push
```

### Bootstrap CONTRIBUTING + About section

```bash
# Édition manuelle de README.md, ajout des badges shields.io
gh repo edit --description "MLOps pipeline industrializing an ML NBA classifier on Kubernetes (kind + Airflow + Prometheus/Grafana)" \
             --add-topic kubernetes --add-topic airflow --add-topic mlops \
             --add-topic data-engineering --add-topic fastapi
```

---

## Vague 2 — Developer Experience

### Création du Makefile

```bash
# Cibles principales créées :
make help              # liste auto-générée depuis les commentaires ## des cibles
make all
make cluster-up / cluster-down
make build
make nba / monitoring / airflow
make port-forward-*
make status
make destroy
```

### Migration de la structure k8s/ vers Kustomize

```bash
# Avant : un seul dossier k8s/ avec tous les manifests à plat
# Après :
k8s/
├── base/                      # manifests communs
│   └── kustomization.yaml
└── overlays/
    ├── dev/
    │   ├── kustomization.yaml
    │   ├── frontend-nodeport.yaml      # patch NodePort
    │   └── image-pull-policy-never.yaml
    ├── staging/README.md
    └── prod/README.md
```

### Tester le rendu Kustomize avant apply

```bash
kubectl kustomize k8s/overlays/dev | less
# ou avec validation :
kubectl kustomize k8s/overlays/dev | kubeval --strict --ignore-missing-schemas
```

---

## Vague 2bis — Migration Minikube → kind

### Création du cluster kind

```bash
# k8s/kind-config.yaml : 1 control-plane + 1 worker, port mapping 30081
kind create cluster --config k8s/kind-config.yaml \
  --image kindest/node:v1.32.2@sha256:36187f6c542fa9b78d2d499de4c857249c5a0ac8cc2241bef2ccd92729a7a259
```

### Chargement d'image dans kind (pas de registry)

```bash
docker build -t nba-backend:1.2 ./nba-api
kind load docker-image nba-backend:1.2 --name nba-predictor
```

> **Pourquoi pas de registry ?** Pour un projet local, la registry ajoute de la complexité (gestion auth, push/pull lent). `kind load` copie directement l'image dans le containerd des nodes.

### Décision Airflow logs en emptyDir (kind RWO only)

Dans `airflow-values.yaml` :
```yaml
logs:
  persistence:
    enabled: false   # PVC RWX pas supporté par rancher.io/local-path
```
Sinon les PVC logs restent `Pending` indéfiniment.

---

## Vague 3 — CI/CD GitHub Actions

### Trois workflows créés

```bash
.github/workflows/
├── ci.yml                # lint + test + yaml + k8s-validate + hadolint
├── docker.yml            # build + Trivy + SARIF + push GHCR
└── k8s-integration.yml   # kind + apply + smoke tests
```

### Tester les workflows en local (act)

```bash
# Optionnel — Tests en local avec nektos/act (lourd, à utiliser ponctuellement)
act push --job python-lint    # joue ci.yml::python-lint
act push -W .github/workflows/docker.yml  # joue tout docker.yml
```

### Configuration GHCR (push d'images)

```bash
# Requis pour que le workflow docker.yml puisse push :
# 1. Repo PUBLIC (sinon Code Scanning + GHCR demandent GitHub Advanced Security $49/u/m)
gh repo edit --visibility public

# 2. Activer le push de Packages via GITHUB_TOKEN (déjà par défaut sur public repos)

# 3. Activer "Code scanning" dans Settings → Code security
# (sinon upload SARIF fail avec 403)
```

### Debug d'un workflow qui fail

```bash
gh run list --workflow=docker.yml --limit 5
gh run view <run-id> --log-failed
gh run view <run-id> --log | grep -i error
```

### Migration trivy-action → install manuel

Après 4 échecs successifs de `aquasecurity/trivy-action` (versions, deps, install.sh), bascule définitive vers install apt :
```yaml
- name: Install Trivy
  run: |
    sudo apt-get install -y wget apt-transport-https gnupg lsb-release
    wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key \
      | sudo gpg --dearmor -o /usr/share/keyrings/trivy.gpg
    echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] \
      https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" \
      | sudo tee /etc/apt/sources.list.d/trivy.list
    sudo apt-get update && sudo apt-get install -y trivy
```

### Pre-commit hooks alignés CI

```bash
pre-commit install
pre-commit run --all-files   # vérifier que tout passe avant push
```

---

## Vague 4.1 — SealedSecrets

### Installer le controller dans le cluster

```bash
make sealed-secrets-install
# = helm upgrade --install sealed-secrets sealed-secrets/sealed-secrets \
#     --namespace kube-system \
#     --set fullnameOverride=sealed-secrets-controller \
#     --wait --timeout 3m
```

### Créer / éditer un Secret en clair (jamais commité)

```bash
# k8s/secrets/airflow-credentials.unsealed.yaml est gitignored
# Y mettre 3 ressources Secret K8s avec stringData
```

### Sceller les Secrets

```bash
make seal-secrets
# Génère k8s/base/airflow-credentials-sealedsecret.yaml (committable)
git add k8s/base/airflow-credentials-sealedsecret.yaml
git commit -m "chore: regen SealedSecret après rotation password postgres"
```

### Appliquer les SealedSecret committés (auto via `make airflow`)

```bash
make apply-sealed-secrets
# = kubectl apply -f k8s/base/airflow-credentials-sealedsecret.yaml
#   + wait que les 3 Secrets K8s soient déchiffrés par le controller
```

### Vérifier le déchiffrement

```bash
kubectl get sealedsecret -n airflow
kubectl get secret -n airflow | grep airflow-
# Doit afficher airflow-postgres-secret, airflow-metadata-secret, airflow-admin-secret

# Voir le contenu déchiffré (debug local seulement, ne jamais copier-coller)
kubectl get secret airflow-postgres-secret -n airflow \
  -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d
```

### Backup master key (CRITIQUE)

```bash
kubectl get secret -n kube-system \
  -l sealedsecrets.bitnami.com/sealed-secrets-key \
  -o yaml > sealed-secrets-master.key
# Stocker en safe offline (1Password, USB chiffré, KeePass)
# Sans cette key, tous les SealedSecret committés sont inutilisables après re-install controller
```

### Restaurer la master key

```bash
# Désinstaller le controller actuel (s'il existe avec une autre key)
helm uninstall sealed-secrets -n kube-system

# Restaurer la key, puis réinstaller le controller (il la réutilisera)
kubectl apply -f sealed-secrets-master.key
make sealed-secrets-install
```

---

## Vague 4.2 — Dockerfile distroless + Trivy bloquant

### Build de l'image distroless

```bash
docker build -t nba-backend:1.2 ./nba-api

# Vérifier la taille (~424 MB, vs 459 MB pour python:3.10-slim)
docker images nba-backend
```

### Scan Trivy local (avant de pusher)

```bash
# Scan complet HIGH/CRITICAL, ignore les CVE OS unfixed
docker run --rm -v //var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:latest image \
  --severity HIGH,CRITICAL \
  --ignore-unfixed \
  --format table \
  nba-backend:1.2

# Avec le .trivyignore du projet (= ce que fait la CI)
docker run --rm -v //var/run/docker.sock:/var/run/docker.sock \
  -v "${PWD}:/work" -w /work \
  aquasec/trivy:latest image \
  --severity HIGH,CRITICAL \
  --ignore-unfixed \
  --ignorefile .trivyignore \
  --exit-code 1 \
  nba-backend:1.2

# Exit code 0 = CI passera ; exit code 1 = nouvelle CVE non triée
```

### Auditer le contenu d'une image distroless (debug)

```bash
# Distroless n'a pas de shell -- utiliser la variante :debug
docker run --rm --entrypoint /busybox/sh \
  gcr.io/distroless/python3-debian12:debug-nonroot \
  -c "python3 --version && ls /usr/lib/python3.11"
```

### Tester l'image localement (smoke test container)

```bash
docker run -d -p 8090:8080 --name nba-test nba-backend:1.2
sleep 5
curl -sf "http://localhost:8090/api/nba/predict?TOV=2&GP=82&MIN=28&PTS=14&FGM=5&FGA=11&FGP=0.45&PM=2&PA=5&PAP=0.40&FTM=2&FTA=3&FTP=0.67&OREB=1&DREB=4&REB=5&AST=4&STL=1&BLK=0.5"
docker rm -f nba-test
```

### Mettre à jour `.trivyignore` après audit trimestriel

```bash
# 1. Relancer le scan complet (sans --ignorefile)
docker run --rm -v //var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:latest image \
  --severity HIGH,CRITICAL --ignore-unfixed \
  nba-backend:1.2

# 2. Pour chaque CVE listée dans .trivyignore :
#    - check si fixée upstream (cf. lien NVD ou rebuild de l'image distroless)
#    - si oui : retirer du .trivyignore, rebuild → la CI doit passer toute seule
#    - si non : pousser le 'Revisit by:' date de 3 mois
```

---

## Vague 4.3 — NetworkPolicies + Calico

### Recréer le cluster avec Calico (nécessaire 1 fois)

```bash
# 1. Détruire l'ancien cluster (avec kindnet)
make cluster-down

# 2. Recréer avec disableDefaultCNI: true (k8s/kind-config.yaml)
#    make cluster-up enchaîne kind create + calico-install automatiquement
make cluster-up
# Output attendu :
#   [OK] Cluster cree (CNI non installe, nodes NotReady).
#   > Installation de Calico v3.28.2 (tigera-operator)...
#   > Attente que les nodes deviennent Ready (calico-node DaemonSet)...
#   [OK] Calico installe, NetworkPolicies effectives.

# 3. Vérifier
kubectl get nodes
# Doit afficher Ready (pas NotReady)
kubectl get pods -n calico-system
# calico-node DaemonSet × 2, calico-kube-controllers, etc.
```

### Re-sealer les Secrets après cluster recréé (master key change)

```bash
make sealed-secrets-install
make seal-secrets
git add k8s/base/airflow-credentials-sealedsecret.yaml
git commit -m "chore: regen SealedSecret après recréation cluster"
```

### Tester l'isolation (intrus dans default → backend = deny)

```bash
# Doit timeout (deny effectif par default-deny-ingress sur ns nba)
kubectl run intrus --image=curlimages/curl -n default --rm -i --restart=Never --timeout=20s --quiet -- \
  curl -m 5 -o /dev/null -w "HTTP %{http_code}\n" \
  http://nba-backend-svc.nba.svc.cluster.local:8080/
# Attendu : HTTP 000 + Connection timed out
```

### Tester un flow autorisé (frontend → backend)

```bash
FRONT=$(kubectl get pod -n nba -l app=nba-frontend -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n nba $FRONT -- curl -sf -m 5 \
  http://nba-backend-svc.nba.svc.cluster.local:8080/
# Attendu : {"message":"Le serveur NBA prediction conçu par Ketsia MULAPI a démarré !"}
```

### Tester un flow cross-namespace (scheduler airflow → backend nba)

```bash
kubectl exec -n airflow airflow-scheduler-0 -c scheduler -- python -c "
import urllib.request
r = urllib.request.urlopen('http://nba-backend-svc.nba.svc.cluster.local:8080/api/nba/predict?TOV=2&GP=82&MIN=28&PTS=14&FGM=5&FGA=11&FGP=0.45&PM=2&PA=5&PAP=0.40&FTM=2&FTA=3&FTP=0.67&OREB=1&DREB=4&REB=5&AST=4&STL=1&BLK=0.5', timeout=5)
print(r.read().decode())
"
# Attendu : {"prediction":{"decision":[1.0]}}
# Autorisé par allow-backend-ingress avec namespaceSelector role=orchestration
```

### Vérifier que Prometheus scrape bien le backend

```bash
# Port-forward Prometheus
kubectl port-forward -n monitoring svc/kube-prom-kube-prometheus-prometheus 9090:9090 &
sleep 3

# Query l'API targets
curl -sf "http://localhost:9090/api/v1/targets" | python -c "
import json, sys
data = json.load(sys.stdin)
nba = [t for t in data['data']['activeTargets'] if 'nba-backend' in t.get('scrapePool', '')]
print(f'Targets actifs nba-backend: {len(nba)}')
for t in nba:
    print(f'  health={t[\"health\"]} url={t[\"scrapeUrl\"]}')
"
# Attendu : 2 targets up (1 par replica backend)

kill %1   # arrêter le port-forward
```

### Debug : voir les denials Calico

```bash
kubectl logs -n calico-system -l k8s-app=calico-node --tail=50 | grep -iE "deny|drop|policy"
```

---

## Vague 4.4 — HPA + metrics-server

### Installer metrics-server

```bash
make metrics-server-install
# Patch --kubelet-insecure-tls obligatoire sur kind (certs self-signed)
# kubectl top nodes / pods devient fonctionnel
```

### Tester que les metrics remontent

```bash
kubectl top nodes
# Doit afficher CPU(cores) et MEMORY(bytes), pas "metrics not available yet"

kubectl top pods -n nba
# nba-backend-xxx  3m  145Mi
```

### Observer le HPA (idle)

```bash
kubectl get hpa -n nba
# nba-backend  Deployment/nba-backend  cpu: 3%/70%  2  5  2  ...

# Détail complet
kubectl describe hpa nba-backend -n nba
```

### Lancer la démo de scale-up sous charge

```bash
make load-test
# 50 workers curl en parallèle pendant 60s sur /api/nba/predict

# Dans un autre terminal :
kubectl get hpa,pods -n nba -w
```

**Résultat attendu** :
```
[T+0s ] cpu: 3%/70%   2 replicas (idle)
[T+22s] cpu: 86%/70%  2 replicas (au-dessus threshold)
[T+38s] cpu: 97%/70%  2 → 3 replicas (SCALE-UP)
[T+48s] cpu: 82%/70%  3 replicas (stabilisé)
[T+70s] cpu: 14%/70%  3 replicas (attente 300s stabilizationWindow)
```

### Forcer un scale-down rapide (debug)

```bash
# Patch temporaire pour réduire stabilizationWindowSeconds
kubectl patch hpa nba-backend -n nba --type=merge -p '{"spec":{"behavior":{"scaleDown":{"stabilizationWindowSeconds":30}}}}'

# Re-apply pour revenir à la valeur du manifest
kubectl apply -k k8s/overlays/dev
```

---

## Vague 4.5 — Ingress + PDB

### Installer ingress-nginx (controller)

```bash
make ingress-install
# = kubectl apply -f https://...ingress-nginx/controller-v1.11.3/.../kind/deploy.yaml
# Le manifest "kind" configure hostPort 80/443 sur le node label ingress-ready=true
```

### Configurer la résolution DNS `nba.localhost`

```bash
# Linux / macOS
echo "127.0.0.1 nba.localhost" | sudo tee -a /etc/hosts

# Windows (PowerShell admin)
Add-Content -Path "C:\Windows\System32\drivers\etc\hosts" -Value "127.0.0.1 nba.localhost"

# Test
ping nba.localhost   # doit répondre depuis 127.0.0.1
```

### Tester l'Ingress

```bash
# Avec résolution DNS (production)
curl -sf "http://nba.localhost/api/nba/predict?TOV=2&GP=82&MIN=28&PTS=14&FGM=5&FGA=11&FGP=0.45&PM=2&PA=5&PAP=0.40&FTM=2&FTA=3&FTP=0.67&OREB=1&DREB=4&REB=5&AST=4&STL=1&BLK=0.5"

# Sans modifier /etc/hosts (utile CI ou debug)
curl -sf --resolve "nba.localhost:80:127.0.0.1" "http://nba.localhost/api/nba/predict?..."

# Ou avec Host header
curl -sf -H "Host: nba.localhost" "http://localhost/api/nba/predict?..."
```

### Vérifier l'état des PodDisruptionBudgets

```bash
kubectl get pdb -n nba
# nba-backend    1  N/A  1  ← 2 replicas, 1 peut tomber lors d'un drain
# nba-frontend   1  N/A  0  ← 1 replica seul, 0 peut tomber (non-évictable)
```

### Simuler un drain de node (test PDB)

```bash
# Drain volontaire d'un node
kubectl drain nba-predictor-worker --ignore-daemonsets --delete-emptydir-data

# Le backend (replicas=2, minAvailable=1) va voir un pod migrer sur l'autre node
# Le frontend (replicas=1, minAvailable=1) va BLOQUER le drain (non-évictable)
# C'est volontaire et documenté.

# Annuler le drain
kubectl uncordon nba-predictor-worker
```

### Recréation cluster pour V4.5 (port mapping change)

```bash
# Le port mapping 30081 -> 80/443 demande une recréation
make cluster-down
make cluster-up        # nouveau cluster avec ports 80/443 + label ingress-ready=true
make sealed-secrets-install
make seal-secrets      # IMPORTANT : nouvelle master key, regen obligatoire
make metrics-server-install
make ingress-install
make build
make monitoring
make nba
make airflow
# OU plus simplement :
make all   # enchaîne tout dans le bon ordre
```

---

## Vague 5 — Dashboard + Alerting

### Déployer le dashboard + les alertes (inclus dans make monitoring)

```bash
make monitoring
# Inclut désormais :
#   - ConfigMap grafana-dashboard-nba (label grafana_dashboard=1)
#   - PrometheusRule nba-backend-alerts (4 alertes)
#   - webhook-demo + AlertmanagerConfig
```

### Vérifier le dashboard dans Grafana

```bash
# Récupérer le password admin (PAS forcément 'prom-operator', le chart le régénère)
kubectl get secret kube-prom-grafana -n monitoring -o jsonpath='{.data.admin-password}' | base64 -d

make port-forward-grafana   # http://localhost:3000
# Dashboards > "NBA Predictor — API Overview"

# Ou via l'API
PASS=$(kubectl get secret kube-prom-grafana -n monitoring -o jsonpath='{.data.admin-password}' | base64 -d)
curl -s -u "admin:$PASS" "http://localhost:3000/api/dashboards/uid/nba-predictor-api" | python -m json.tool
```

### Vérifier que le sidecar a chargé le dashboard

```bash
GRAFANA=$(kubectl get pod -n monitoring -l app.kubernetes.io/name=grafana -o jsonpath='{.items[0].metadata.name}')
kubectl logs -n monitoring $GRAFANA -c grafana-sc-dashboard --tail=10 | grep -i nba
# "Writing /tmp/dashboards/nba-overview.json"
```

### Vérifier que les règles d'alerte sont chargées

```bash
kubectl get prometheusrule -n monitoring nba-backend-alerts

# Via l'API Prometheus
kubectl port-forward -n monitoring svc/kube-prom-kube-prometheus-prometheus 9090:9090 &
curl -sf "http://localhost:9090/api/v1/rules" | python -c "
import json, sys
d = json.load(sys.stdin)
for g in d['data']['groups']:
    if 'nba' in g['name'].lower():
        for r in g['rules']:
            print(f'{r[\"name\"]} [{r.get(\"state\")}]')"
# Au repos : 4 alertes [inactive]
```

### Déclencher une alerte pour démo (NBABackendDown)

```bash
# 1. Supprimer le HPA (sinon il re-scale) + scaler à 0
kubectl delete hpa nba-backend -n nba
kubectl scale deployment/nba-backend -n nba --replicas=0

# 2. Attendre ~1min30 (l'alerte a un 'for: 1m')
kubectl port-forward -n monitoring svc/kube-prom-kube-prometheus-prometheus 9090:9090 &
# Observer le passage pending -> firing dans http://localhost:9090/alerts

# 3. Vérifier qu'Alertmanager a reçu
kubectl port-forward -n monitoring svc/kube-prom-kube-prometheus-alertmanager 9093:9093 &
curl -sf "http://localhost:9093/api/v2/alerts" | python -c "import json,sys; print([a['labels']['alertname'] for a in json.load(sys.stdin)])"

# 4. Vérifier que le webhook a reçu la notification
kubectl logs -n monitoring -l app=alertmanager-webhook-demo --tail=100 | grep NBABackendDown

# 5. RESTAURER (recrée backend + HPA depuis Kustomize)
kubectl apply -k k8s/overlays/dev
kubectl rollout status deployment/nba-backend -n nba
# Le webhook reçoit alors la notification 'resolved' (sendResolved: true)
```

### Suivre les alertes reçues par le webhook en temps réel

```bash
kubectl logs -n monitoring -l app=alertmanager-webhook-demo -f
# Chaque POST d'Alertmanager est loggé en JSON (alertname, status, labels...)
```

---

## Opérations quotidiennes

### Voir le status global

```bash
make status   # pods, services des 3 namespaces
```

### Suivre les logs

```bash
make logs-backend     # streaming des 2 replicas backend
make logs-frontend
make logs-airflow     # scheduler uniquement (le plus parlant)

# Manuel pour un pod précis :
kubectl logs -f -n nba <pod-name> --tail=100
kubectl logs -f -n airflow -l component=api-server --tail=50
```

### Port-forward des UIs

```bash
make port-forward-airflow   # http://localhost:8081 (admin/admin)
make port-forward-grafana   # http://localhost:3000 (admin/prom-operator)
# Ctrl+C pour arrêter
```

### Rebuild rapide après modif code backend

```bash
make build                       # docker build + kind load
kubectl rollout restart deployment/nba-backend -n nba
kubectl rollout status deployment/nba-backend -n nba --timeout=120s
```

### Sync des DAGs après modif locale

```bash
make sync-dags   # kubectl cp dags/*.py vers airflow-scheduler-0
# Le dag-processor détecte le changement dans ~30s
```

### Lancer le DAG manuellement

```bash
# Via UI : http://localhost:8081 → DAGs → nba_orchestration → Trigger DAG
# Via CLI :
kubectl exec -n airflow airflow-scheduler-0 -c scheduler -- \
  airflow dags trigger nba_orchestration
```

### Tester les routes API en local

```bash
# Prédiction par stats individuelles (via Ingress V4.5)
curl -sf "http://nba.localhost/api/nba/predict?TOV=2&GP=82&MIN=28&PTS=14&FGM=5&FGA=11&FGP=0.45&PM=2&PA=5&PAP=0.40&FTM=2&FTA=3&FTP=0.67&OREB=1&DREB=4&REB=5&AST=4&STL=1&BLK=0.5"

# Prédiction par nom
curl -sf "http://nba.localhost/api/nba/info?Name=Brandon%20Ingram"

# Doc OpenAPI Swagger
open http://nba.localhost/docs    # macOS
start http://nba.localhost/docs   # Windows

# Pré-requis : '127.0.0.1 nba.localhost' dans /etc/hosts (ou systemd-resolved récent)
```

### Lancer les tests pytest

```bash
pytest                           # 33 tests, ~3s
pytest --cov=nba-api             # avec coverage
pytest -k "predict"              # filtré sur les tests qui matchent
pytest tests/test_api.py -v      # un fichier précis, verbose
```

### Lint / format manuel (= ce que fait pre-commit + CI)

```bash
ruff check .                     # lint
ruff format --check .            # format check (sans modifier)
ruff format .                    # format apply
mypy nba-api dags                # type check strict
```

---

## Dépannage

### "Cannot connect to the Docker daemon"

```powershell
# Docker Desktop n'est pas démarré
# → ouvrir Docker Desktop manuellement, attendre la baleine en bas à droite
```

### Nodes restent `NotReady` après `kind create cluster`

Cause : `disableDefaultCNI: true` dans `kind-config.yaml` → pas de CNI = pas de réseau pod.

```bash
# Solution : installer Calico
make calico-install
# Ou plus simple : utiliser make cluster-up (l'enchaîne automatiquement)
```

### `kind load docker-image` échoue avec "failed to detect containerd snapshotter"

Spécifique au runner GitHub Actions (mismatch containerd entre runner et node kind).

```bash
# Workaround : passer par un tarball
docker save -o /tmp/nba-backend.tar nba-backend:1.2
kind load image-archive /tmp/nba-backend.tar --name nba-predictor
# En local (WSL/Docker Desktop), kind load docker-image direct marche
```

### SealedSecret reste en `SealingStatus: Error`

Cause possible : la master key du controller a changé (réinstallation), le SealedSecret est chiffré avec l'ancienne clé.

```bash
# Vérifier l'erreur
kubectl describe sealedsecret <name> -n <namespace>

# Solution : re-sealer
make seal-secrets
kubectl apply -f k8s/base/airflow-credentials-sealedsecret.yaml
```

### Pods Airflow Pending (logs PVC)

Cause : on a oublié `logs.persistence.enabled: false` dans `airflow-values.yaml`. Le PVC RWX reste Pending sur kind (provisioner local en RWO).

```bash
# Vérifier
kubectl get pvc -n airflow
# airflow-logs Pending → confirmer

# Solution : éditer airflow-values.yaml, désactiver la persistence, helm upgrade
helm upgrade airflow apache-airflow/airflow -n airflow -f airflow-values.yaml
```

### Smoke test 30080 ou 30081 échoue (timeout)

Le NodePort 30080 a été supprimé en V4.3, et 30081 en V4.5 (Ingress).

```bash
# Solution V4.5 : tout passe par l'Ingress nba.localhost
curl -sf "http://nba.localhost/api/nba/predict?TOV=2&GP=82&..."

# Si nba.localhost ne résout pas → ajouter à /etc/hosts
echo "127.0.0.1 nba.localhost" | sudo tee -a /etc/hosts

# Ou tester sans modifier hosts
curl -sf --resolve "nba.localhost:80:127.0.0.1" "http://nba.localhost/api/nba/predict?..."
```

### Ingress retourne 404

```bash
# Vérifier que le controller est Ready
kubectl get pods -n ingress-nginx
# ingress-nginx-controller-xxx  1/1  Running

# Vérifier l'Ingress
kubectl get ingress -n nba
# ADDRESS doit être 'localhost' (sinon le controller n'est pas reachable)

# Vérifier les logs du controller
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller --tail=30
```

### HPA reste à `<unknown>/70%`

```bash
# Cause #1 : metrics-server pas installé ou en CrashLoop
kubectl get deployment metrics-server -n kube-system
kubectl logs -n kube-system -l k8s-app=metrics-server --tail=20

# Cause #2 : pas de 'resources.requests' sur le Deployment
kubectl get deployment nba-backend -n nba -o jsonpath='{.spec.template.spec.containers[0].resources}'
# Doit afficher requests + limits
```

### Prometheus ne scrape pas le backend

3 causes courantes :

```bash
# 1. ServiceMonitor sans le bon label
kubectl get servicemonitor nba-backend -n monitoring -o yaml | grep release
# Doit afficher: release: kube-prom

# 2. NetworkPolicy bloque le scrape (V4.3)
kubectl get namespace monitoring --show-labels
# Doit afficher: role=monitoring
kubectl label namespace monitoring role=monitoring --overwrite

# 3. Prometheus n'a pas reload sa config (rare)
kubectl rollout restart statefulset/prometheus-kube-prom-kube-prometheus-prometheus -n monitoring
```

### Dashboard NBA n'apparaît pas dans Grafana

```bash
# 1. Le ConfigMap a-t-il le bon label ?
kubectl get configmap grafana-dashboard-nba -n monitoring --show-labels
# Doit contenir grafana_dashboard=1

# 2. Le sidecar l'a-t-il chargé ?
GRAFANA=$(kubectl get pod -n monitoring -l app.kubernetes.io/name=grafana -o jsonpath='{.items[0].metadata.name}')
kubectl logs -n monitoring $GRAFANA -c grafana-sc-dashboard --tail=20 | grep -i nba

# 3. Forcer un reload (supprimer/recréer le ConfigMap)
kubectl delete configmap grafana-dashboard-nba -n monitoring
make monitoring
```

### Login Grafana refusé (mot de passe)

```bash
# Le password n'est PAS toujours 'prom-operator' — le récupérer :
kubectl get secret kube-prom-grafana -n monitoring -o jsonpath='{.data.admin-password}' | base64 -d
```

### Alerte ne fire pas

```bash
# 1. PrometheusRule chargée ? (label release: kube-prom obligatoire)
kubectl get prometheusrule nba-backend-alerts -n monitoring -o yaml | grep -A2 labels

# 2. La query PromQL renvoie-t-elle des données ?
# Tester dans http://localhost:9090/graph la query de l'alerte

# 3. AlertmanagerConfig chargé ? (label release: kube-prom aussi)
kubectl get alertmanagerconfig -n monitoring
```

### DAG `nba_orchestration` n'apparaît pas dans Airflow UI

```bash
# 1. Vérifier qu'il est dans le PVC dags
kubectl exec -n airflow airflow-scheduler-0 -c scheduler -- ls /opt/airflow/dags/

# 2. Sinon re-sync
make sync-dags

# 3. Vérifier les logs du dag-processor (parse errors)
kubectl logs -n airflow -l component=dag-processor --tail=50
```

### `make build` échoue avec "ezwinports.make ne respecte pas SHELL"

Spécifique à Windows si `SHELL := bash.exe` (chemin relatif).

```bash
# Solution : le Makefile force le chemin absolu sur Windows
ifeq ($(OS),Windows_NT)
SHELL := C:/Program Files/Git/bin/bash.exe
.SHELLFLAGS := -c
endif
# Si Git n'est pas installé là, adapter le chemin ou installer Git for Windows :
winget install Git.Git
```

### Couleurs ANSI affichées en littéral (`\033[36m`)

Cause : `cmd.exe` n'interprète pas les codes ANSI.

```bash
# Solution : Makefile force bash + utilise printf (pas echo)
# Si le problème persiste, vérifier que C:\Program Files\Git\bin existe
```

### Caractères accentués affichés en mojibake

Cause : `cp1252` par défaut sur PowerShell vs UTF-8 des messages.

```bash
# Solution : les messages Makefile sont volontairement désaccentués
# (Makefile utilise "creation" au lieu de "création")
# Pour les commit messages, idem (faciliter cross-OS)
```

---

## Pour aller plus loin

- **Référence technique complète** → [doc.md](doc.md)
- **Vitrine + quickstart** → [README.md](../README.md)
- **Install des outils** → [PREREQUISITES.md](PREREQUISITES.md)
- **Rapport projet V3** → [Rapport projet orchestra nba_predictor.pdf](Rapport%20projet%20orchestra%20nba_predictor.pdf)
