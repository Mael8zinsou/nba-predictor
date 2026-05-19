# CLAUDE.md — instructions pour Claude (assistant IA)

> Fichier d'index et de contraintes pour les sessions Claude Code.
> **Pour la doc technique → [docs/doc.md](docs/doc.md)** (référence profonde, source de vérité).
> **Pour les commandes par vague → [docs/key_commands.md](docs/key_commands.md)**.
> Ce fichier liste uniquement ce dont j'ai besoin pour collaborer efficacement sur ce projet.

---

## Contexte projet (résumé)

Projet d'industrialisation d'une application ML de classification de joueurs NBA (cours "Infrastructures et orchestration de données", YNOV, Ketsia Mulapi Tita). Auteur de la partie orchestration/infra : Maël M. ZINSOU. Le code applicatif original (API + frontend) est de Ketsia Mulapi.

L'objectif n'est pas le modèle ML (régression logistique simple, déjà entraînée et sérialisée dans `classifier.pikl`), mais le **pipeline d'industrialisation** : conteneurisation, orchestration Kubernetes, automatisation Airflow, observabilité Prometheus/Grafana, sécurité réseau.

**État au 2026-05-19** : Vagues 1 à 4.5 terminées (cluster + sécurité + secrets + NP + HPA + Ingress + PDB). V5 (observabilité avancée), V6 (Data Engineering MLflow), V7 (présentation portfolio) restantes.

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

- **Toucher au modèle `classifier.pikl` ou au dataset `nba_logreg.csv`** hors du contexte Vague 6 (pipeline d'entraînement MLflow).
- **"Corriger" `preprocess()` au passage** : le fix doit venir avec son scaler sérialisé en V6, sinon on casse les prédictions sans pouvoir re-générer le modèle. Le xfail strict du test `test_single_vector_uses_dataset_statistics` est le rappel.
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
