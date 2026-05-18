# Dockerfile multi-stage distroless pour le backend NBA (Vague 4.2).
#
# Objectifs :
#   - Réduire drastiquement les CVE upstream de python:3.10-slim (CVE-free target)
#   - Image runtime sans shell ni package manager (réduction de la surface d'attaque)
#   - User non-root par défaut (UID 65532)
#   - Permettre la ré-activation de Trivy --exit-code 1 dans la CI Docker
#
# Choix techniques :
#   - Stage builder = python:3.11-slim : compile les wheels (numpy, scikit-learn,
#     pandas) dans /install. On a besoin d'un shell + pip ici.
#   - Stage runtime = gcr.io/distroless/python3-debian12:nonroot : Python 3.11.2
#     minimal (~50 MB), pas de shell, pas d'apt. Le python natif distroless sert
#     d'interpréteur ; on lui injecte les site-packages via PYTHONPATH.
#   - Cohérence ABI Python 3.11 : wheels cp311 du builder = compatibles avec le
#     Python 3.11 du runtime (patch-level peut différer, c'est l'ABI mineure qui
#     compte). On ne copie PAS de binaire Python du builder, juste les libs.
#   - CMD = exec form avec module uvicorn lancé via -m, pas de wrapper shell.
#
# Notes :
#   - Le pickle classifier.pikl (sklearn 0.24.1) reste chargeable en sklearn
#     1.5.1 + Python 3.11 (warning InconsistentVersionWarning toujours silencé
#     côté pytest, cf. pyproject.toml).
#   - Pas de healthcheck Docker explicite : Kubernetes gère les liveness/readiness
#     probes côté Deployment.

# --- Stage 1 : builder ---
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /build

COPY requirements.txt .

# Install dans un préfixe isolé qu'on copie tel quel dans le runtime.
# --prefix=/install évite la pollution du Python système du builder.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2 : runtime distroless ---
FROM gcr.io/distroless/python3-debian12:nonroot

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Injecte les site-packages compilés par le builder dans le PYTHONPATH du
# python natif distroless. Le chemin /install/lib/python3.11/site-packages
# vient du --prefix=/install du stage builder.
ENV PYTHONPATH=/install/lib/python3.11/site-packages

WORKDIR /app

# Libs Python + binaires console-scripts (utiles pour debug, pas pour le CMD)
COPY --from=builder --chown=nonroot:nonroot /install /install
COPY --chown=nonroot:nonroot . /app

EXPOSE 8080

# CMD exec form : on utilise le python natif distroless (entrypoint par défaut
# = /usr/bin/python3.11) avec uvicorn lancé en module.
CMD ["-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
