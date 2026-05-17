FROM python:3.14-slim

# Éviter le buffering (logs Airflow / K8s lisibles)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie tout le contenu du répertoire de build (le contexte Docker) vers le répertoire de travail du conteneur.
# Autrement dit, "COPY . ." signifie : copier "ici" (.) vers "ici" (.) dans l'image (généralement WORKDIR).
# Sert à embarquer le code applicatif et les fichiers nécessaires dans l'image au moment du build.
# Remarque : le contenu peut être filtré via un fichier .dockerignore.
COPY . .

# Port API
EXPOSE 8080

# Lancement API
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]