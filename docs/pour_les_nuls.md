# NBA Predictor — pour les nuls

> Tu sors d'un bootcamp web, tu connais Git, HTTP, npm/pip, tu as peut-être déjà déployé un site sur Vercel ou Heroku. Mais quand tu regardes ce projet, tu vois des mots comme **Kubernetes, Calico, sealed-secrets, HPA, ingress-nginx** et tu te demandes ce que c'est que ce bazar. Ce document est pour toi.
>
> Objectif : tu sors d'ici en comprenant **pourquoi** chacun de ces outils existe et **ce qu'il résout**. Pas le détail technique (ça c'est dans [doc.md](doc.md)), juste la logique.
>
> Promesse : zéro YAML dans ce document. Que des analogies.

---

## Sommaire

1. [Le projet en 1 minute](#1-le-projet-en-1-minute)
2. [Le problème : pourquoi un `.py` qui marche ne suffit pas](#2-le-problème--pourquoi-un-py-qui-marche-ne-suffit-pas)
3. [Docker : la boîte Tupperware](#3-docker--la-boîte-tupperware)
4. [Kubernetes : le chef d'orchestre](#4-kubernetes--le-chef-dorchestre)
5. [kind : un mini-orchestre dans ton PC](#5-kind--un-mini-orchestre-dans-ton-pc)
6. [Helm vs Kustomize : recettes vs variantes](#6-helm-vs-kustomize--recettes-vs-variantes)
7. [Apache Airflow : le robot calendrier](#7-apache-airflow--le-robot-calendrier)
8. [Prometheus + Grafana : capteurs et tableau de bord](#8-prometheus--grafana--capteurs-et-tableau-de-bord)
9. [La sécurité : trois cadenas](#9-la-sécurité--trois-cadenas)
10. [CI/CD : le robot relecteur](#10-cicd--le-robot-relecteur)
11. [HPA + Ingress : la voiture qui s'adapte au trafic](#11-hpa--ingress--la-voiture-qui-sadapte-au-trafic)
12. [Glossaire de survie](#12-glossaire-de-survie)

---

## 1. Le projet en 1 minute

Imagine une appli web simple : tu rentres les stats d'un joueur NBA (points, rebonds, passes…) et l'appli te dit s'il aura une carrière de plus de 5 ans. C'est de la **prédiction machine learning** : un modèle entraîné qui sort un "oui/non".

Cette appli existe déjà (créée par Ketsia MULAPI en 2021). Elle a :
- Un **backend** en Python qui héberge le modèle (FastAPI)
- Un **frontend** en HTML/JS pour le formulaire (servi par Nginx)
- Un **modèle** sérialisé (`classifier.pikl`, un objet Python sauvegardé sur disque)

**Ce qu'on a fait en plus** : transformer cette appli "qui marche en local" en **vraie infrastructure de production**. C'est ça, ce projet.

Concrètement :
- L'appli tourne dans un **cluster Kubernetes** (on va voir ce que c'est)
- Elle est **automatisée** : un robot la lance toutes les nuits pour faire des prédictions
- Elle est **surveillée** : des graphiques montrent combien de requêtes elle traite, sa latence, sa consommation
- Elle est **sécurisée** : aucun pod inconnu ne peut lui parler, ses mots de passe sont chiffrés
- Elle est **élastique** : si beaucoup de monde s'y connecte, elle se dédouble toute seule
- Elle est **testée automatiquement** à chaque fois qu'on touche le code

Voilà. Le reste du document explique pourquoi on a besoin de tout ça.

---

## 2. Le problème : pourquoi un `.py` qui marche ne suffit pas

Tu as un script `app.py` qui tourne sur ton PC. Tu lances `python app.py`, ton navigateur ouvre `http://localhost:8080`, ça marche. **Pourquoi pas juste le copier sur un serveur ?**

Réponse courte : parce qu'un serveur, ce n'est pas ton PC.

Réponse longue : sur ton PC, tu as :
- Une certaine version de Python (3.11, 3.12, peu importe)
- Des bibliothèques installées avec `pip install` (numpy, fastapi, sklearn…) dans des versions précises
- Des variables d'environnement bien configurées
- Un système d'exploitation (Windows, Linux, macOS)

Sur le serveur, **rien de tout ça n'est garanti**. Et même si tu installes les bonnes versions, dans 6 mois tu auras oublié quoi installer exactement.

Et si l'appli marche sur **un** serveur mais qu'elle reçoit 1000 utilisateurs en même temps ? Le serveur lâche. Il faut en mettre 5 en parallèle. Comment savoir lequel répond ? Comment savoir si un est en panne ?

C'est exactement les problèmes que les outils suivants résolvent.

---

## 3. Docker : la boîte Tupperware

**Analogie** : imagine que ton appli est un repas. Pour qu'elle marche, il faut le plat lui-même (ton code), les ingrédients (les bibliothèques Python), et la cuisine équipée (Python 3.11, certains paquets système). Plutôt que de te trimballer la cuisine entière à chaque déménagement, tu mets le tout dans une **boîte Tupperware étanche** : le repas avec tous ses accompagnements, prêt à être ouvert n'importe où.

**Cette boîte Tupperware, c'est une image Docker.**

Tu écris un fichier `Dockerfile` qui dit : "Prends Python 3.11, copie mon code, installe ces 12 bibliothèques, lance `uvicorn` au démarrage". Docker construit alors une **image** : un fichier auto-suffisant qui contient TOUT ce qu'il faut pour faire tourner ton appli, identique partout.

Quand tu veux lancer l'appli, tu démarres un **container** à partir de cette image. Un container, c'est l'image "en train de tourner". Tu peux lancer 1, 5, 100 containers depuis la même image.

**Dans ce projet** :
- `nba-api/Dockerfile` construit l'image du backend Python
- `nba-web/Dockerfile` construit l'image du frontend Nginx
- L'image backend pèse 424 MB (tout inclus : Python, sklearn, pandas, le modèle…)

**Bonus sécurité** : on utilise une image **distroless** pour le backend. C'est une image sans shell (pas de `bash`), sans gestionnaire de paquets (pas de `apt`), avec seulement Python et le strict nécessaire. Résultat : si un attaquant arrive à exécuter du code dans le container, il ne peut quasiment rien faire (pas de `curl` pour télécharger d'autres outils, pas de shell pour explorer le système). C'est comme un Tupperware **scellé** : on peut ouvrir, mais on ne peut rien y ajouter.

---

## 4. Kubernetes : le chef d'orchestre

OK, on a des images Docker. Maintenant, on veut **les faire tourner en production**, avec :
- 5 containers backend qui se partagent la charge
- 1 container frontend qui sert le HTML
- Un container Postgres pour la base de données
- Une logique qui dit "si un container crash, redémarre-le automatiquement"
- Une logique qui dit "si la charge augmente, lance plus de containers"
- Un truc qui dit "le frontend doit pouvoir parler au backend"

Faire tout ça à la main, c'est invivable. C'est exactement ce que fait **Kubernetes** (souvent abrégé K8s — K + 8 lettres + s).

**Analogie** : Kubernetes est un **chef d'orchestre**. Toi, tu lui donnes une partition (tes manifestes YAML) qui dit "je veux 5 violons, 2 pianos, 1 batterie". Lui s'occupe de :
- Faire venir les musiciens (lancer les containers)
- Remplacer un musicien qui part (redémarrer un container qui crash)
- Faire monter le son si l'auditoire grossit (autoscaling)
- Faire passer le micro entre les musiciens (réseau interne)
- S'assurer que tout joue ensemble (synchronisation)

**Vocabulaire essentiel** :
- **Pod** : la plus petite unité Kubernetes = 1 ou plusieurs containers qui tournent ensemble (généralement 1 seul). Si ton container backend tourne, il est dans un Pod.
- **Deployment** : "je veux N pods de ce type, surveille-les". Si un pod crash, le Deployment en relance un.
- **Service** : "comment les autres pods peuvent te joindre ?" — donne une adresse interne stable (un peu comme un nom de domaine interne).
- **Namespace** : un dossier pour organiser. Dans ce projet, on a 3 namespaces : `nba` (l'appli), `airflow` (l'orchestration), `monitoring` (la supervision).
- **Cluster** : l'ensemble de machines (physiques ou virtuelles) sur lesquelles Kubernetes tourne. Peut être 1 machine ou 1000.

**Dans ce projet** :
- L'appli NBA a 1 Deployment frontend (1 pod) + 1 Deployment backend (2 pods minimum)
- Le backend peut grimper à 5 pods sous charge (voir section HPA plus bas)
- Tout est organisé dans le namespace `nba`

---

## 5. kind : un mini-orchestre dans ton PC

Kubernetes en vrai, ça tourne sur des dizaines de serveurs cloud (AWS EKS, Google GKE, Azure AKS). Mais pour développer et apprendre, payer un cluster cloud c'est cher et lent.

**kind** = "Kubernetes IN Docker". C'est un outil qui fait tourner un cluster Kubernetes **complet, mais à l'intérieur de containers Docker sur ton PC**. Le cluster croit qu'il est en vrai prod, alors qu'il est juste dans Docker Desktop sur ton laptop.

**Analogie** : kind, c'est un **simulateur de vol** pour Kubernetes. Tu apprends à piloter un Airbus sans risquer de crash, et quand tu passes en vrai, c'est les mêmes commandes.

**Dans ce projet** :
- `kind create cluster` crée un mini-cluster (2 nodes : 1 control-plane + 1 worker)
- Les nodes sont en fait des containers Docker visibles dans Docker Desktop
- Tu peux tout casser, tout reconstruire, en 30 secondes

**Limite à connaître** : kind utilise `kindnet` par défaut comme réseau. C'est un réseau "qui marche" mais qui ne respecte pas certaines règles de sécurité avancées (les NetworkPolicies, voir plus bas). Donc dans ce projet, on remplace kindnet par **Calico** (un autre système de réseau qui respecte ces règles).

---

## 6. Helm vs Kustomize : recettes vs variantes

Tu écris ces fameux fichiers YAML pour décrire ce que Kubernetes doit faire (les "manifestes"). Mais souvent, tu veux **la même chose avec des petites variations** : en dev tu veux 1 replica, en prod tu veux 5. En dev tu veux des logs verbose, en prod non.

Tu pourrais copier-coller tes YAML et changer les valeurs. Mais quand tu modifies, tu dois changer aux 3 endroits. Bug garanti.

Deux outils résolvent ça :

### Helm = recette de cuisine

**Analogie** : Helm est un livre de recettes. La recette dit "préparer un gâteau, voici les étapes, et tu peux choisir le parfum (chocolat, vanille, fraise)". Tu donnes les paramètres, Helm génère le gâteau final.

Les "recettes" s'appellent des **charts**. Il existe des milliers de charts publics : un chart pour Apache Airflow, un chart pour Prometheus, un chart pour PostgreSQL. Tu installes le chart, tu lui passes tes valeurs (`values.yaml`), il génère tous les YAML K8s nécessaires.

**Dans ce projet** : on utilise Helm uniquement pour les **outils déjà existants** (Airflow, Prometheus/Grafana, sealed-secrets). Pas besoin de réinventer la roue.

### Kustomize = patches sur une base

**Analogie** : Kustomize est un outil de **collage**. Tu as une base (les YAML "de base"), et tu peux appliquer des **patches** dessus pour chaque variante. "En dev, change cette ligne". "En prod, ajoute ces 3 lignes".

**Dans ce projet** : on utilise Kustomize pour **notre appli NBA** (4 manifestes maison). C'est plus léger que Helm pour ce volume. On a une base (`k8s/base/`) et un overlay dev (`k8s/overlays/dev/`).

**Règle qu'on s'est fixée** : Helm pour les charts upstream, Kustomize pour notre code. Chacun fait ce qu'il fait le mieux.

---

## 7. Apache Airflow : le robot calendrier

Le backend est dispo, super. Mais on veut le **solliciter automatiquement** : par exemple chaque matin à 6h, faire une prédiction sur un nouveau joueur et stocker le résultat. Ou : tous les lundis, recalculer toutes les prédictions sur la liste complète des joueurs NBA.

Tu pourrais utiliser un `cron` Linux. Mais quand tu as 10 tâches qui s'enchaînent ("d'abord ça, puis si succès ça, sinon ça"), `cron` devient ingérable. Pas de vue d'ensemble, pas de logs centralisés, pas de retry automatique.

**Airflow** est un **robot calendrier sous stéroïdes**. Tu décris tes workflows en Python (appelés **DAGs** = Directed Acyclic Graphs, mais retiens juste "diagramme de tâches"). Airflow s'occupe de :
- Lancer les tâches au bon moment
- Gérer les dépendances entre tâches ("la tâche B attend la tâche A")
- Garder l'historique des exécutions
- Te montrer une belle UI pour superviser
- Réessayer automatiquement si une tâche échoue

**Dans ce projet** :
- Un DAG `nba_orchestration` qui appelle `GET /api/nba/predict`
- L'UI Airflow est dispo via `make port-forward-airflow` → `http://localhost:8081`
- Login : `admin / admin` (en local uniquement, sinon c'est une faute de sécurité)

Pour fonctionner, Airflow a besoin d'une **base de données** (pour stocker l'historique des runs, les DAGs, les utilisateurs). On lui donne un PostgreSQL dédié dans le même namespace.

---

## 8. Prometheus + Grafana : capteurs et tableau de bord

Quand ton appli est en prod, tu veux savoir :
- Combien de requêtes elle reçoit par seconde ?
- Quelle est la latence (temps de réponse) ?
- Combien de RAM/CPU elle consomme ?
- Combien de pods sont vivants ?
- Est-ce qu'il y a des erreurs 500 qui montent ?

Sans monitoring, tu découvres les pannes quand les utilisateurs te le disent. Pas idéal.

**Prometheus** = un outil qui va **interroger** tes pods régulièrement (toutes les 15 secondes par défaut) pour leur demander leurs métriques. Chaque pod expose une URL `/metrics` qui dit "tiens, voici mes compteurs actuels". Prometheus aspire tout ça et stocke dans une base de données interne.

**Analogie** : Prometheus est comme un **infirmier qui prend la tension** à chaque patient toutes les 15 secondes et note dans son cahier.

**Grafana** = un outil pour **visualiser** les données stockées par Prometheus. Belles courbes, alertes, dashboards customisables.

**Analogie** : Grafana est le **tableau de bord d'une voiture**. Vitesse, niveau d'essence, température moteur. Les données viennent des capteurs (Prometheus), mais c'est le tableau de bord qui te les rend lisibles.

**Dans ce projet** :
- Le backend FastAPI expose `/metrics` avec 2 compteurs : `nba_api_requests_total` (combien de requêtes) et `nba_api_request_latency_seconds` (combien de temps elles prennent)
- Prometheus est installé via le chart Helm `kube-prometheus-stack` (qui installe aussi Grafana et l'opérateur qui gère tout ça)
- Un objet K8s appelé **ServiceMonitor** dit à Prometheus "voici un nouveau truc à scraper"
- Grafana est dispo via `make port-forward-grafana` → `http://localhost:3000` (login `admin / prom-operator`)

---

## 9. La sécurité : trois cadenas

Ton appli en prod, tout le monde sur Internet va pouvoir taper dessus. Et même à l'intérieur du cluster, tu ne veux pas qu'un container compromis puisse accéder à n'importe quoi. Trois couches de défense ont été mises en place.

### Cadenas 1 : les images sont propres (Trivy + distroless)

**Le problème** : ton image Docker contient peut-être 250 failles de sécurité connues. Pas dans **ton** code, mais dans les bibliothèques système (le shell, la libc, le SSL…) que l'image trimballe.

**La solution** :
- **Distroless** (vu plus haut) : on enlève tout ce qui n'est pas strictement nécessaire. Pas de shell, pas d'apt, pas de bash. Moins de surface = moins de failles.
- **Trivy** : un outil qui scanne ton image et liste toutes les failles connues. On l'a configuré pour **faire échouer la CI** si une nouvelle faille HIGH/CRITICAL apparaît.
- Les failles qu'on ne peut pas corriger (parce qu'elles viennent de l'image distroless Google) sont listées explicitement dans un fichier `.trivyignore`, **avec une date d'expiration** ("re-checker dans 3 mois").

**Analogie** : c'est comme un **portique de sécurité à l'aéroport**. Tout ce qui passe est scanné. Si on détecte un objet interdit, on bloque. Et la liste des objets interdits est régulièrement mise à jour.

### Cadenas 2 : le réseau est isolé (NetworkPolicies + Calico)

**Le problème** : par défaut dans Kubernetes, **tous les pods peuvent parler à tous les pods**. Si un attaquant compromet n'importe quel pod (même un pod inoffensif), il peut se balader partout : taper sur la base de données, sur le backend interne, etc.

**La solution** : **NetworkPolicies**. Ce sont des règles de pare-feu au niveau Kubernetes. On définit explicitement qui peut parler à qui. Pattern "**zero-trust**" : par défaut, **rien n'est autorisé**. Puis on ajoute des règles "le frontend peut parler au backend", "Prometheus peut parler à `/metrics`", etc.

**Analogie** : c'est passer d'**un open space** (tout le monde voit tout le monde) à un **immeuble avec des badges** (tu rentres dans ton étage uniquement, et il faut un badge spécial pour aller au coffre).

Mais attention : kindnet (le réseau par défaut de kind) ne sait pas appliquer ces règles. Il faut le remplacer par **Calico**, un autre système de réseau qui sait les appliquer pour de vrai.

**Test concret** : on a vérifié qu'un pod intrus dans un namespace `default` qui essaie de taper sur la base Postgres se prend un timeout. Le pare-feu marche.

### Cadenas 3 : les secrets sont chiffrés (sealed-secrets)

**Le problème** : ton appli a besoin de mots de passe (pour la base de données, pour des APIs externes). Si tu les mets en clair dans tes fichiers YAML et que tu commit sur GitHub, **le monde entier les voit**. Catastrophe.

**La solution** : **sealed-secrets**. Tu mets le mot de passe dans un fichier qui n'est **jamais commit** (`*.unsealed.yaml`, dans `.gitignore`). Tu lances une commande `kubeseal` qui chiffre ce fichier avec une clé publique. Le résultat (`*-sealedsecret.yaml`) est **incompréhensible sans la clé privée** du cluster.

Tu commit le fichier chiffré tranquillement sur GitHub. Quand tu le déploies dans Kubernetes, un petit programme dans le cluster (le **controller**) déchiffre le secret et le rend disponible aux pods.

**Analogie** : c'est comme **envoyer un message à une boîte aux lettres dont seul Bob a la clé**. N'importe qui peut envoyer le message (le fichier chiffré est public sur GitHub), mais seul Bob (le controller dans le cluster) peut le lire.

**Limite importante à connaître** : si tu **perds la clé privée** du controller (par exemple en réinstallant le cluster), tous tes secrets chiffrés deviennent inutilisables. Il faut donc **sauvegarder cette clé** en lieu sûr (USB chiffrée, gestionnaire de mots de passe).

---

## 10. CI/CD : le robot relecteur

**Le problème** : à chaque fois que tu modifies ton code, tu dois :
- Faire passer les tests
- Vérifier que ton code respecte les règles de style (linter)
- Construire l'image Docker
- La scanner pour les failles
- La pousser dans un registre
- Vérifier que l'ensemble se déploie correctement

Si tu fais ça à la main à chaque commit, tu vas en oublier la moitié. Et un jour, tu vas pousser un bug en prod.

**CI/CD** = "Continuous Integration / Continuous Deployment". C'est un **robot** (hébergé sur GitHub Actions, GitLab CI, Jenkins…) qui fait tout ça à ta place, à **chaque commit**.

**Dans ce projet** : 3 workflows GitHub Actions (3 robots, en parallèle).

### Robot 1 : `ci.yml` — le linter du quotidien

À chaque push, 5 jobs lancés en parallèle :
- Lint du code Python (Ruff)
- Type-checking (Mypy strict)
- Tests automatisés (Pytest)
- Lint des YAML
- Lint des Dockerfile

Si un seul fail, ton commit est marqué avec une croix rouge sur GitHub.

### Robot 2 : `docker.yml` — le constructeur d'images

- Construit l'image Docker
- Scan Trivy (cadenas 1)
- Pousse l'image sur le registre **GHCR** (GitHub Container Registry)
- Upload le résultat du scan dans l'onglet "Security" de GitHub (visibilité gratuite)

### Robot 3 : `k8s-integration.yml` — le testeur de déploiement

- Crée un mini cluster kind dans la VM GitHub
- Installe Calico, metrics-server, ingress-nginx
- Déploie l'appli NBA
- Appelle l'API avec un curl
- Si l'API ne répond pas correctement → CI rouge

**Analogie** : c'est comme avoir un **stagiaire perfectionniste** qui relit ton code à chaque commit, le teste, le construit, et te crie dessus si quelque chose cloche.

**Bonus** : **Dependabot**, un autre robot qui propose chaque lundi des mises à jour de tes bibliothèques. On a configuré pour qu'il ne propose que les mises à jour mineures (pas les majors qui cassent tout).

---

## 11. HPA + Ingress : la voiture qui s'adapte au trafic

Dernière brique : que se passe-t-il si **beaucoup d'utilisateurs** arrivent en même temps ?

### HPA : multiplie tes pods automatiquement

**HPA** = HorizontalPodAutoscaler. C'est un objet K8s qui surveille la charge CPU de tes pods. Si la moyenne dépasse 70%, il **ajoute des pods automatiquement**. Si la charge redescend, il en supprime.

**Analogie** : ton restaurant a 2 serveurs (pods). À midi, 100 clients arrivent. Tu sors le téléphone et tu appelles 3 serveurs en renfort (scale-up). Quand la nuit tombe, ils rentrent chez eux (scale-down). Toi (le manager), tu ne fais rien — c'est automatique.

**Dans ce projet** : on a montré que sous charge artificielle (50 utilisateurs fictifs qui tapent en boucle pendant 60s), le backend passe de 2 à 3 pods en moins d'une minute.

### Ingress : la porte d'entrée unique

**Le problème** : si tes pods sont accessibles directement (chacun avec son port), c'est le bazar pour les utilisateurs ("vous voulez le frontend ? c'est port 30081. L'API admin ? port 30082. Le truc de debug ? port 30083.").

**Ingress** = un objet K8s qui dit "**tout le trafic externe passe par moi**, et je redirige selon l'URL". Tu accèdes à `https://mon-site.com/` → frontend. `https://mon-site.com/api/...` → backend. `https://mon-site.com/admin` → page admin. **Une seule porte d'entrée**, plusieurs destinations.

**Analogie** : Ingress, c'est **le hall d'accueil d'un grand hôtel**. Tu rentres par la porte principale, puis le concierge te dirige vers la chambre, le restaurant, le spa…

Dans ce projet :
- On a un ingress-controller (nginx-ingress) qui écoute sur le port 80
- Une règle dit "`nba.localhost/...` → frontend"
- Le frontend nginx fait ensuite le sous-routing `/api/*` vers le backend

### PDB : assure-toi qu'il reste toujours quelqu'un

**PDB** = PodDisruptionBudget. Une règle qui dit "même quand tu fais de la maintenance (drain de nodes, upgrade…), **garde au moins 1 pod en vie**". Évite le cas catastrophique où tu fais une mise à jour et où Kubernetes éteint tous tes pods en même temps.

**Analogie** : c'est un panneau "**laissez toujours un serveur en cuisine**" pendant que tu réorganises l'équipe.

---

## 12. Glossaire de survie

| Terme | Traduction simple |
|---|---|
| **Container** | Une instance d'une image Docker en train de tourner |
| **Image** | La "boîte Tupperware" : code + dépendances + OS minimal, sérialisée |
| **Pod** | 1 (ou plusieurs) containers tournant ensemble dans Kubernetes |
| **Deployment** | "Je veux N pods de ce type, surveille-les" |
| **Service** | Une adresse interne stable pour joindre un ensemble de pods |
| **Namespace** | Un dossier pour organiser les ressources dans le cluster |
| **Cluster** | L'ensemble des machines sur lesquelles Kubernetes tourne |
| **Node** | Une machine du cluster (physique ou VM) |
| **YAML** | Le format texte utilisé pour décrire tout ce que Kubernetes fait (sensible aux espaces, attention !) |
| **kubectl** | La commande pour parler à Kubernetes (`kubectl get pods`, `kubectl logs`…) |
| **Helm** | Le gestionnaire de paquets pour Kubernetes |
| **Chart** | Un paquet Helm (= une recette d'installation) |
| **Manifeste** | Un fichier YAML qui décrit une ressource K8s |
| **CRD** | Custom Resource Definition : un type d'objet K8s ajouté par un outil tiers (ex: ServiceMonitor) |
| **Ingress** | La porte d'entrée HTTP du cluster |
| **CNI** | Container Network Interface : le système qui gère le réseau entre pods (kindnet, Calico, Cilium…) |
| **HPA** | HorizontalPodAutoscaler : ajuste auto le nombre de pods |
| **PDB** | PodDisruptionBudget : garantie de dispo pendant maintenance |
| **NetworkPolicy** | Règle de pare-feu interne au cluster |
| **Secret** | Un objet K8s qui stocke des valeurs sensibles (mots de passe, tokens) |
| **SealedSecret** | Un Secret chiffré, committable sur Git |
| **DAG** | Directed Acyclic Graph : un workflow Airflow |
| **Métrique** | Une valeur numérique exposée par une appli (compteur, jauge, latence…) |
| **Scrape** | Action de Prometheus pour récupérer les métriques d'une appli |
| **CI/CD** | Les robots qui testent et déploient ton code automatiquement |
| **distroless** | Image Docker minimaliste sans shell ni gestionnaire de paquets |
| **kustomize** | Outil pour appliquer des patches sur des YAML K8s |
| **kind** | Kubernetes IN Docker : cluster K8s qui tourne dans Docker Desktop |

---

## Pour continuer

Tu as les bases. Si tu veux creuser :

- **Comment ça marche techniquement, pour de vrai ?** → [doc.md](doc.md)
- **Quelles commandes exactes ont été lancées à chaque étape ?** → [key_commands.md](key_commands.md)
- **Comment je fais marcher tout ça sur mon PC ?** → [PREREQUISITES.md](PREREQUISITES.md) puis `make all`

Et si tu veux apprendre Kubernetes en partant de zéro avec un vrai tuto progressif, ces ressources gratuites sont excellentes :
- [Kubernetes The Hard Way](https://github.com/kelseyhightower/kubernetes-the-hard-way) (avancé, mais formateur)
- [killercoda.com](https://killercoda.com/playgrounds/scenario/kubernetes) (terminaux interactifs gratuits)
- Le tutoriel officiel : [kubernetes.io/docs/tutorials/](https://kubernetes.io/docs/tutorials/)

Bonne route. Et rappelle-toi : tout ça paraît compliqué au début, mais chaque outil résout un vrai problème. Une fois que tu as compris **pourquoi** il existe, le **comment** vient tout seul.
