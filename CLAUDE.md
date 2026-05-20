# CLAUDE.md — instructions pour Claude (assistant IA)

> Fichier d'index et de contraintes pour les sessions Claude Code.
> **Pour la doc technique → [docs/doc.md](docs/doc.md)** (référence profonde, source de vérité).
> **Pour les commandes par vague → [docs/key_commands.md](docs/key_commands.md)**.
> Ce fichier liste uniquement ce dont j'ai besoin pour collaborer efficacement sur ce projet.

---

## Contexte projet (résumé)

Projet d'industrialisation d'une application ML de classification de joueurs NBA (cours "Infrastructures et orchestration de données", YNOV, Ketsia Mulapi Tita). Auteur de la partie orchestration/infra : Maël M. ZINSOU. Le code applicatif original (API + frontend) est de Ketsia Mulapi.

L'objectif n'est pas le modèle ML (régression logistique simple, déjà entraînée et sérialisée dans `classifier.pikl`), mais le **pipeline d'industrialisation** : conteneurisation, orchestration Kubernetes, automatisation Airflow, observabilité Prometheus/Grafana, sécurité réseau.

**État au 2026-05-20** : Vagues 1 à 6 (cœur) terminées (cluster + sécurité + secrets + NP + HPA + Ingress + PDB + observabilité + pipeline d'entraînement reproductible MLflow + fix `preprocess()`). Reste : déploiement serveur MLflow dans le cluster (V6 in-progress), V7 (présentation portfolio).

Pour tous les détails techniques (architecture, stack, conventions, ADR, bugs connus) → **[docs/doc.md](docs/doc.md)**.

---

## Environnement de dev

- **Plateforme principale : Windows + PowerShell** (utiliser la syntaxe PowerShell pour les commandes shell). Le cluster Kubernetes tourne via `kind` dans Docker Desktop.
- Le Makefile force `SHELL := C:/Program Files/Git/bin/bash.exe` sur Windows car `ezwinports.make` ne respecte pas `SHELL` avec un chemin relatif et `cmd.exe` ne gère pas les codes ANSI / UTF-8.
- Python 3.10 pour la CI et le dev local (`requirements-dev.txt`), **Python 3.11 dans le backend distroless** (cf. `nba-api/Dockerfile`).
- Pour tester l'API en local hors K8s : `cd nba-api ; uvicorn app:app --reload --port 8080` puis ouvrir `http://localhost:8080/docs`.

---

## Workflow de développement

- **Pre-commit hooks installés** : `pre-commit install` à la racine. Toute modif passe par ruff, ruff-format, yamllint, hadolint, detect-secrets avant `git commit`.
- **Tests locaux** : `pytest` depuis la racine (33 tests, 1 xfailed attendu, ~3s). `pytest --cov=nba-api` pour la coverage.
- **Lint manuel** : `ruff check . && ruff format --check . && mypy nba-api dags`.
- **Avant chaque push** : vérifier `pytest` + `ruff` localement, sinon la CI fail.
- **Convention de commits** : préfixes `feat(vX.Y):`, `fix(ci):`, `chore(deps):`, etc. Les commit messages sont volontairement désaccentués pour faciliter cross-OS.

---

## Ce que je ne dois PAS faire sans confirmation

- **Régénérer `classifier.pikl` / `scaler.pikl` sans relancer `training/train.py`** : ces deux artefacts sont produits ensemble par le pipeline reproductible (V6). Ne jamais en éditer un seul à la main. L'ancien modèle est archivé en `classifier.legacy-0.24.1.pikl` (rollback).
- **Désynchroniser `FEATURE_ORDER` (training/train.py) de `build_params()` (functions.py)** : c'est l'invariant critique du projet — le modèle et l'API doivent partager l'ordre exact des 19 features (finissant par TOV). Une désync casse silencieusement les prédictions.
- **Modifier `.trivyignore` sans ajouter de date `Revisit by:`** — chaque ignore doit avoir une échéance d'audit pour éviter d'accumuler de la dette CVE silencieuse.
- **Supprimer les `__pycache__/` ou autres caches versionnés** sans vérifier d'abord ce qui est effectivement utile.
- **Mettre à jour la documentation utilisateur sans synchroniser les 3 fichiers** : `README.md` (vitrine), `docs/doc.md` (référence technique), `docs/key_commands.md` (cookbook). Si un changement impacte les conventions ou décisions, mettre à jour `docs/doc.md` en priorité.

Note : le code applicatif de Ketsia (`functions.py`, frontend) est librement refactorable depuis le 2026-05-16 (cf. `memory/feedback_app_code_refactor_allowed.md`).

---

## Pointers utiles

- **Architecture, ADR, bugs connus** → [docs/doc.md](docs/doc.md)
- **Commandes par vague + dépannage** → [docs/key_commands.md](docs/key_commands.md)
- **Vulgarisation pour profil non-infra** → [docs/pour_les_nuls.md](docs/pour_les_nuls.md)
- **Roadmap des vagues à venir** → section Roadmap du [README.md](README.md)
- **Layout du repo (vue d'ensemble)** → §4 de [docs/doc.md](docs/doc.md#4-structure-du-repository)
