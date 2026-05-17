# Overlay : prod (placeholder)

Stub prêt à étendre pour un déploiement production sur cluster managé (GKE/EKS/AKS).

Pistes :
- 3+ replicas backend, PodDisruptionBudget, topologySpreadConstraints
- NetworkPolicies strictes entre namespaces
- Secrets via SOPS ou sealed-secrets (jamais en clair)
- Ingress + TLS (cert-manager + Let's Encrypt)
- Resource limits stricts + ResourceQuota namespace
- HPA + VPA

Voir [overlays/dev/kustomization.yaml](../dev/kustomization.yaml) comme modèle.
