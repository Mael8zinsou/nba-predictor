# Checklist mise en ligne GitHub

Fichier opérationnel à supprimer (ou archiver) une fois le repo créé et configuré sur GitHub.

## 1. Init et premier push

```bash
# Depuis la racine du repo
git init                    # déjà fait
git add .
git commit -m "feat: initial public release — NBA Predictor MLOps pipeline"

# Créer le repo distant (gh CLI installé)
gh repo create nba-predictor --public \
  --description "MLOps pipeline: FastAPI ML app industrialized with Kubernetes, Airflow, Prometheus, Grafana" \
  --source=. --remote=origin --push

# OU manuellement : créer le repo sur https://github.com/new puis
# git remote add origin git@github.com:<user>/nba-predictor.git
# git branch -M main
# git push -u origin main
```

## 2. Topics à configurer (Settings → About)

Lot principal validé : `mlops`, `kubernetes`, `airflow`, `prometheus`, `fastapi`, `helm`

Via CLI :
```bash
gh repo edit --add-topic mlops,kubernetes,airflow,prometheus,fastapi,helm
```

## 3. About section (Settings → About)

- **Description** : `MLOps pipeline: industrializing an ML classification app with Kubernetes, Airflow, Prometheus, Grafana on Minikube`
- **Website** : laisser vide pour l'instant (à remplir quand GitHub Pages sera activé)
- ☑️ Releases
- ☑️ Packages
- ☐ Deployments (pas encore)

## 4. Repository settings recommandés

- **Settings → General** :
  - ☑️ Issues
  - ☑️ Discussions (utile pour Q&A sans créer d'issues)
  - ☐ Wikis (le README + docs/ suffisent)
  - ☐ Projects (overkill pour ce scope)

- **Settings → Pull Requests** :
  - ☑️ Allow squash merging (recommandé par défaut)
  - ☐ Allow merge commits
  - ☑️ Automatically delete head branches

- **Settings → Branches → Branch protection rules** (sur `main`) :
  - ☑️ Require pull request before merging
  - ☑️ Require status checks to pass (à activer après la mise en place de la CI Vague 3)

## 5. (Optionnel) GitHub Pages pour publier graph.html

Si tu veux exposer la visualisation graphify en ligne :

```bash
# Construire d'abord le graphe (cf. /graphify)
/graphify . --mode deep

# Activer Pages depuis Settings → Pages :
#   Source : Deploy from branch
#   Branch : main / docs/ (ou créer une branche gh-pages)
# Puis copier graphify-out/graph.html → docs/index.html
cp graphify-out/graph.html docs/index.html
git add docs/index.html
git commit -m "docs: publish graphify visualization to GitHub Pages"
git push
```

L'URL sera `https://<user>.github.io/nba-predictor/` après ~1 min.

## 6. Une fois en ligne

- Mettre à jour le lien GitHub de Ketsia dans le README racine (section "Crédit") avec son vrai profil si tu l'as
- Ajouter une release v0.1.0 (`gh release create v0.1.0 --notes "Initial public release"`)
- Épingler le repo sur ton profil GitHub
- Supprimer ce fichier (`rm docs/GITHUB_SETUP.md`) une fois la config terminée
