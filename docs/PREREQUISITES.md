# Prérequis et installation des outils

Ce document détaille les versions et commandes d'installation des outils nécessaires pour déployer le projet NBA Predictor en local.

## Vue d'ensemble

| Outil | Version testée | Rôle |
|---|---|---|
| [Docker Desktop](https://docs.docker.com/get-docker/) | ≥ 20.10 | Build des images applicatives + runtime du cluster kind |
| [kind](https://kind.sigs.k8s.io/) | ≥ 0.20 | Cluster Kubernetes local (Kubernetes-in-Docker) |
| [kubectl](https://kubernetes.io/docs/tasks/tools/) | ≥ 1.28 | Client CLI Kubernetes |
| [Helm](https://helm.sh/) | ≥ 3.12 | Gestion des charts (Airflow, kube-prometheus-stack) |
| [GNU Make](https://www.gnu.org/software/make/) | ≥ 4.0 | Exécution du `Makefile` (orchestration des commandes) |
| [kubeseal](https://github.com/bitnami-labs/sealed-secrets) | ≥ 0.27 | Chiffrement des Secrets K8s (regénération des SealedSecret) |

**Pourquoi kind plutôt que Minikube ?** kind crée son cluster directement dans des conteneurs Docker (pas de VM séparée), donc :
- Les conteneurs du cluster apparaissent dans Docker Desktop (suivi visuel)
- Démarrage plus rapide (~30s vs ~2 min)
- Pas de `eval $(minikube docker-env)` à gérer
- Workflow images : `docker build` → `kind load docker-image` → déployable

**Ressources Docker Desktop recommandées** : 4 CPU, 8 Go RAM minimum (Docker Desktop → Settings → Resources). Sans ça, héberger app + Airflow + kube-prometheus-stack en parallèle sera trop juste.

---

## Installation par OS

### Windows

Le moyen le plus simple : [winget](https://learn.microsoft.com/fr-fr/windows/package-manager/) (intégré à Windows 10+).

```powershell
winget install Docker.DockerDesktop
winget install Kubernetes.kind
winget install Kubernetes.kubectl
winget install Helm.Helm
winget install ezwinports.make
```

Alternative : [Chocolatey](https://chocolatey.org/install) (PowerShell admin) :

```powershell
choco install -y docker-desktop kind kubernetes-cli kubernetes-helm make
```

Ou [Scoop](https://scoop.sh/) (sans admin) :

```powershell
scoop install kind kubectl helm make kubeseal
# Docker Desktop : à installer depuis docker.com
```

**kubeseal manuellement (si pas de Scoop)** :

1. Télécharger depuis [github.com/bitnami-labs/sealed-secrets/releases](https://github.com/bitnami-labs/sealed-secrets/releases) → `kubeseal-X.X.X-windows-amd64.tar.gz`
2. Extraire `kubeseal.exe` dans un dossier déjà dans le `Path` (ex. `C:\Users\<toi>\bin`)
3. Vérifier : `kubeseal --version`

> **Quand est-ce nécessaire ?** Uniquement pour **regénérer** un `SealedSecret` (rotation de password, ajout d'une clé). Le déploiement standard (`make all`) ne consomme que les `SealedSecret` déjà committés. kubeseal n'est donc pas indispensable pour un premier déploiement à partir du repo.

**Notes Windows** :
- Démarre Docker Desktop avant la première commande `make` (sinon `kind create cluster` échoue : pas de daemon).
- Le `Makefile` détecte Windows et bascule automatiquement sur Git Bash (chemin : `C:\Program Files\Git\bin\bash.exe`). Si tu n'as pas Git installé, soit installer Git for Windows (`winget install Git.Git`), soit utiliser WSL.
- Pour que les commandes Linux soient dispo dans PowerShell (`awk`, `grep`…), ajouter `C:\Program Files\Git\usr\bin` au `Path` Windows.

### macOS

```bash
# Homebrew (https://brew.sh/)
brew install --cask docker
brew install kind kubectl helm make
```

`make` est généralement déjà installé via les Xcode Command Line Tools.

### Linux (Debian / Ubuntu)

```bash
# Docker Engine
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# kind
curl -Lo ./kind https://kind.sigs.k8s.io/dl/latest/kind-linux-amd64
chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind

# Helm
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# make (généralement déjà présent)
sudo apt-get install -y make
```

### Linux (Fedora / RHEL / CentOS)

```bash
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io
sudo systemctl enable --now docker

# kubectl + kind + helm : mêmes commandes que Debian/Ubuntu ci-dessus
```

---

## Vérification post-installation

```bash
docker --version           # Docker version 20.10+
kind version               # kind v0.20+
kubectl version --client   # Client Version: v1.28+
helm version               # version.BuildInfo{Version:"v3.12+...
make --version             # GNU Make 4.0+
```

Si tout est OK :

```bash
make cluster-up            # Crée le cluster kind (~30s)
make build                 # Build images dans Docker Desktop + kind load
make all                   # Déploie tout (5-10 min)
```

---

## Dépannage courant

### `ERROR: failed to create cluster: ... Cannot connect to the Docker daemon`

Docker Desktop n'est pas démarré. Lancer Docker Desktop puis relancer `make cluster-up`.

### `ImagePullBackOff` sur les pods NBA

Cause : les images ne sont pas dans le cluster kind. Solution : relancer `make build` (qui fait `kind load docker-image` automatiquement). Vérifier après :

```bash
docker exec -it nba-predictor-control-plane crictl images | grep nba
```

### `make: bash.exe: Command not found` (Windows)

Git for Windows n'est pas installé ou pas au chemin attendu. Soit installer Git (`winget install Git.Git`), soit modifier la première ligne `SHELL := ...` du `Makefile` pour pointer vers le bon chemin.

### Helm timeout sur `kube-prometheus-stack`

Le chart télécharge plusieurs images lourdes (Prometheus, Grafana, Alertmanager, exporters). Si timeout sur connexion lente, augmenter dans le Makefile :

```makefile
helm upgrade --install kube-prom ... --wait --timeout 10m  # au lieu de 5m
```

### Pods Airflow en `Init:CrashLoopBackOff`

Cause fréquente : Postgres pas encore prêt. Le `Makefile` attend explicitement (`kubectl wait`) mais en cas de souci, vérifier :

```bash
kubectl get pods -n airflow
kubectl logs -n airflow airflow-postgres-<hash>
kubectl logs -n airflow airflow-scheduler-<hash> -c wait-for-airflow-migrations
```

### Recréer un cluster propre

```bash
make cluster-down          # supprime le cluster kind
make cluster-up            # le recrée from scratch
```
