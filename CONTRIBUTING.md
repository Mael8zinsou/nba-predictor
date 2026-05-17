# Contributing

Merci de votre intérêt pour ce projet ! Ce repo est principalement un **showcase portfolio**, mais les contributions et retours sont les bienvenus.

## Reporter un bug

Ouvrez une [issue GitHub](../../issues/new) en précisant :

- Votre environnement (OS, versions Docker Desktop / kind / kubectl / Helm)
- Les étapes pour reproduire
- Le comportement attendu vs observé
- Les logs pertinents (`kubectl logs`, output Docker, etc.)

## Proposer une amélioration

1. Ouvrez d'abord une issue pour discuter du changement avant d'écrire du code — cela évite les pull requests sans suite.
2. Forkez le repo, créez une branche descriptive : `feat/<sujet>`, `fix/<sujet>`, `docs/<sujet>`.
3. Faites vos changements avec des commits atomiques et messages clairs (format conseillé : [Conventional Commits](https://www.conventionalcommits.org/)).
4. Vérifiez que :
   - Les manifestes Kubernetes restent valides (`kubectl kustomize k8s/overlays/dev`)
   - Le code Python passe ruff + mypy (lancés automatiquement par les pre-commit hooks)
   - Les tests passent (`pytest`)
   - Le README et la doc sont mis à jour si nécessaire
5. Ouvrez une pull request en référençant l'issue.

## Setup développement

```bash
# Dépendances dev (lint, format, type-check, tests)
pip install -r requirements-dev.txt

# Pre-commit hooks (lint + format + secret scan automatiques avant chaque commit)
pre-commit install

# Lancer tous les hooks manuellement (sans commit)
pre-commit run --all-files

# Lancer juste les vérifications individuelles
ruff check .
ruff format --check .
mypy nba-api dags
pytest
```

## Périmètre du projet

Ce repo se concentre sur l'**industrialisation cloud-native** d'une application ML :

- ✅ Améliorations Kubernetes / Helm / Airflow / observabilité
- ✅ CI/CD, tests, sécurité, secrets
- ✅ Documentation, schémas, ADR
- ⚠️ Refonte du modèle ML : possible mais hors scope principal — préférez ouvrir une discussion d'abord
- ⚠️ Refactor majeur du frontend : possible mais le frontend actuel sert avant tout à démontrer le reverse proxy Nginx

Voir la roadmap dans le [README](README.md#roadmap) pour les pistes prioritaires.

## Code de conduite

Soyez courtois et constructif. Les attaques personnelles, propos discriminatoires ou comportements toxiques ne seront pas tolérés. En cas de problème, contactez le mainteneur : [maelzinsou@proton.me](mailto:maelzinsou@proton.me).
