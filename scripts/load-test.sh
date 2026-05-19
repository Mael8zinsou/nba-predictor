#!/usr/bin/env bash
# Load test pour declencher le scale-up du HPA (V4.4).
#
# Strategie : N workers paralleles qui spam GET /api/nba/predict pendant DURATION
# secondes. Avec 50 workers x 60s, on observe typiquement :
#   - CPU pods backend : 3% -> 200%+ (cap a 100% sur 100m requests = 100m utilises)
#   - HPA trigger : averageUtilization > 70%
#   - Scale-up : 2 -> 3 -> 4 -> 5 replicas (par steps de +2 max, periodSeconds 30s)
#
# Usage :
#   ./scripts/load-test.sh [duration_seconds] [parallel_workers]
#   ex : ./scripts/load-test.sh 60 50
#
# Observation en parallele dans un autre terminal :
#   kubectl get hpa -n nba -w
#   kubectl top pods -n nba
#   watch -n 2 'kubectl get hpa,pods -n nba'

set -euo pipefail

DURATION="${1:-60}"
WORKERS="${2:-50}"
URL="http://localhost:30081/api/nba/predict?TOV=2&GP=82&MIN=28&PTS=14&FGM=5&FGA=11&FGP=0.45&PM=2&PA=5&PAP=0.40&FTM=2&FTA=3&FTP=0.67&OREB=1&DREB=4&REB=5&AST=4&STL=1&BLK=0.5"

# Verifier que l'API repond avant de lancer la charge
if ! curl -sf -m 5 "$URL" >/dev/null; then
  echo "ERROR: l'API ne repond pas sur $URL" >&2
  echo "Verifier : kubectl get pods -n nba && kubectl get hpa -n nba" >&2
  exit 1
fi

echo "=== Load test : ${WORKERS} workers en parallele, pendant ${DURATION}s ==="
echo "Cible : $URL"
echo ""
echo "Observer dans un AUTRE terminal :"
echo "  kubectl get hpa,pods -n nba -w"
echo "  kubectl top pods -n nba"
echo ""
echo "Demarrage dans 3s..."
sleep 3

START=$(date +%s)
END=$((START + DURATION))

worker() {
  local id="$1"
  local count=0
  while [ "$(date +%s)" -lt "$END" ]; do
    curl -sf -m 5 -o /dev/null "$URL" && count=$((count + 1)) || true
  done
  echo "  worker $id : $count requetes OK"
}

# Lance N workers en background
for i in $(seq 1 "$WORKERS"); do
  worker "$i" &
done

# Attente fin de tous les workers
wait

ELAPSED=$(($(date +%s) - START))
echo ""
echo "=== Load test termine en ${ELAPSED}s ==="
echo ""
echo "Etat final HPA + pods :"
kubectl get hpa,pods -n nba
echo ""
echo "Le HPA met ~5 min a redescendre (stabilizationWindowSeconds=300)."
echo "Surveiller avec : kubectl get hpa -n nba -w"
