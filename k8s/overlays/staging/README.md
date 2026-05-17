# Overlay : staging (placeholder)

Stub prêt à étendre quand un environnement de pré-production sera ajouté.

Pistes :
- Image tags pinned via `images:` dans kustomization.yaml
- Resources requests/limits explicites
- HorizontalPodAutoscaler basé sur la métrique custom `nba_api_request_latency_seconds`
- Ingress (au lieu de NodePort) avec TLS via cert-manager

Voir [overlays/dev/kustomization.yaml](../dev/kustomization.yaml) comme modèle.
