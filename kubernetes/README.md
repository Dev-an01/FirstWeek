# Kubernetes Deployment for firstweek

This directory contains all Kubernetes manifests and deployment scripts for deploying the firstweek application to Google Kubernetes Engine (GKE).

## Directory Structure

```
kubernetes/
├── README.md                          # This file
├── QUICK_REFERENCE.md                 # Quick command reference
├── base/                              # Base Kubernetes manifests
│   ├── namespace.yaml                 # Namespace definition
│   ├── configmap.yaml                 # Application configuration
│   ├── secrets.yaml                   # Secrets template (DO NOT commit actual values)
│   ├── ingress.yaml                   # Ingress & SSL configuration
│   ├── hpa.yaml                       # Horizontal Pod Autoscalers
│   ├── databases/                     # Database StatefulSets
│   │   ├── avatar-user-db.yaml        # PostgreSQL for users/auth
│   │   ├── rag-postgres.yaml          # PostgreSQL for RAG data
│   │   ├── neo4j.yaml                 # Neo4j graph database
│   │   └── redis.yaml                 # Redis cache
│   └── services/                      # Application Deployments
│       ├── frontend.yaml              # React frontend
│       ├── auth-service.yaml          # Authentication service
│       ├── chat-service.yaml          # Chat service
│       ├── recall-service.yaml        # Recall.ai integration
│       ├── avatar-interface.yaml      # Avatar interface proxy
│       └── rag-api.yaml               # RAG API (GPU workload)
├── overlays/                          # Kustomize overlays (future use)
│   ├── dev/
│   ├── staging/
│   └── production/
└── scripts/                           # Deployment automation scripts
    ├── 0-update-project-id.sh         # Update GCP project ID in all files
    ├── 1-setup-gcp.sh                 # Setup GCP project & APIs
    ├── 2-create-cluster.sh            # Create GKE cluster
    ├── 3-build-images.sh              # Build & push Docker images
    ├── 4-deploy-secrets.sh            # Deploy Kubernetes secrets
    ├── 5-deploy-app.sh                # Deploy all resources
    └── 6-health-check.sh              # Health check & verification
```

## Quick Start

### Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed
- [kubectl](https://kubernetes.io/docs/tasks/tools/) installed
- [Docker](https://docs.docker.com/get-docker/) installed
- GCP account with billing enabled
- Domain name (optional, for Ingress)

### Deployment Steps

1. **Update Project ID**
   ```bash
   cd scripts
   ./0-update-project-id.sh
   # Enter your GCP project ID when prompted
   ```

2. **Setup GCP** (~5 minutes)
   ```bash
   ./1-setup-gcp.sh
   ```

3. **Create GKE Cluster** (~10 minutes)
   ```bash
   ./2-create-cluster.sh
   ```

4. **Build Docker Images** (~20 minutes)
   ```bash
   ./3-build-images.sh
   ```

5. **Configure Secrets**
   ```bash
   # Create .env file with your secrets
   cp ../../.env.example ../../.env
   nano ../../.env  # Edit with actual values

   # Deploy secrets
   ./4-deploy-secrets.sh
   ```

6. **Deploy Application** (~15 minutes)
   ```bash
   ./5-deploy-app.sh
   ```

7. **Verify Deployment** (~2 minutes)
   ```bash
   ./6-health-check.sh
   ```

**Total deployment time: ~50 minutes**

## Documentation

- **[GKE_DEPLOYMENT_GUIDE.md](../GKE_DEPLOYMENT_GUIDE.md)** - Comprehensive deployment guide with troubleshooting
- **[QUICK_REFERENCE.md](./QUICK_REFERENCE.md)** - Quick reference for daily operations
- **[PRODUCTION_SETUP_GUIDE.md](../PRODUCTION_SETUP_GUIDE.md)** - Original Docker Compose setup guide

## Architecture Highlights

### Compute Resources

| Component | Type | Resources | Notes |
|-----------|------|-----------|-------|
| Frontend | Deployment | 2-10 replicas (HPA) | React SPA |
| Backend Services | Deployments | 2-10 replicas each (HPA) | Node.js microservices |
| RAG API | Deployment | 1 replica | GPU workload (Tesla T4) |
| Databases | StatefulSets | 1 replica each | PostgreSQL, Neo4j, Redis |

### Storage

- **Persistent Volumes**: ~150GB total
  - User DB: 20GB
  - RAG DB: 30GB
  - Neo4j: 25GB
  - Redis: 5GB
  - ML Models: 50GB
  - Cache: 20GB

### Networking

- **Internal**: ClusterIP services for inter-service communication
- **External**: Ingress with Google Cloud Load Balancer
- **SSL**: Managed certificate with auto-renewal
- **DNS**: A record pointing to static IP

### Auto-scaling

- **Horizontal Pod Autoscaling (HPA)**: Based on CPU/Memory (70-80% target)
- **Cluster Autoscaling**: Node pools scale 2-10 nodes
- **GPU Pool**: 1-2 nodes (GPU workloads are expensive)

## Cost Estimation

**Monthly cost: ~$483 - $720**

Breakdown:
- Standard nodes: $120-$240
- GPU node (Tesla T4): $300-$350
- Storage: $25-$30
- Load Balancer: $18-$25
- Egress: $10-$50
- Misc (CI/CD, Registry): $10-$25

See [GKE_DEPLOYMENT_GUIDE.md](../GKE_DEPLOYMENT_GUIDE.md#cost-estimation) for cost optimization tips.

## Common Operations

### View Status
```bash
kubectl get all -n firstweek
```

### View Logs
```bash
kubectl logs -f deployment/auth-service -n firstweek
```

### Scale Service
```bash
kubectl scale deployment frontend --replicas=5 -n firstweek
```

### Update Service
```bash
kubectl set image deployment/frontend \
  frontend=gcr.io/PROJECT_ID/frontend:v1.1.0 \
  -n firstweek
```

### Restart Service
```bash
kubectl rollout restart deployment/auth-service -n firstweek
```

### Access Database
```bash
kubectl exec -it statefulset/avatar-user-db -n firstweek -- \
  psql -U postgres -d avatar_user_db
```

See [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) for more commands.

## Troubleshooting

### Pods not starting?
```bash
kubectl describe pod <pod-name> -n firstweek
kubectl logs <pod-name> -n firstweek
```

### GPU not available?
```bash
kubectl get nodes -l cloud.google.com/gke-accelerator
kubectl describe node <gpu-node-name> | grep nvidia
```

### Service not accessible?
```bash
kubectl get svc -n firstweek
kubectl get endpoints -n firstweek
```

### Database connection issues?
```bash
kubectl logs statefulset/avatar-user-db -n firstweek
kubectl exec -it statefulset/avatar-user-db -n firstweek -- \
  pg_isready -U postgres -d avatar_user_db
```

See [GKE_DEPLOYMENT_GUIDE.md](../GKE_DEPLOYMENT_GUIDE.md#troubleshooting) for detailed troubleshooting.

## Security

- **Secrets**: Stored in Kubernetes secrets (consider Google Secret Manager for production)
- **RBAC**: Kubernetes Role-Based Access Control
- **Network Policies**: Restrict pod-to-pod communication
- **Workload Identity**: Secure access to GCP services
- **SSL/TLS**: Managed certificates with auto-renewal
- **Private Container Registry**: Artifact Registry with IAM

## Monitoring

### GCP Console
- **GKE Dashboard**: https://console.cloud.google.com/kubernetes
- **Workloads**: View pod status, logs, metrics
- **Services & Ingress**: View network resources
- **Storage**: View persistent volumes

### kubectl
```bash
# Resource usage
kubectl top pods -n firstweek
kubectl top nodes

# Events
kubectl get events -n firstweek --sort-by='.lastTimestamp'

# Health check
cd scripts && ./6-health-check.sh
```

## CI/CD

### GitHub Actions

See [GKE_DEPLOYMENT_GUIDE.md](../GKE_DEPLOYMENT_GUIDE.md#cicd-pipeline) for complete CI/CD setup with GitHub Actions.

### Cloud Build

Automated builds on commit:
```bash
gcloud builds submit --config=cloudbuild.yaml
```

## Maintenance

### Backup Databases
```bash
kubectl exec statefulset/avatar-user-db -n firstweek -- \
  pg_dump -U postgres avatar_user_db > backup-$(date +%Y%m%d).sql
```

### Update Cluster
```bash
gcloud container clusters upgrade firstweek-cluster \
  --zone=us-central1-a
```

### Scale Cluster
```bash
gcloud container clusters resize firstweek-cluster \
  --node-pool default-pool \
  --num-nodes 4 \
  --zone us-central1-a
```

## Cleanup

**Warning: This will delete everything and is irreversible!**

```bash
# Delete cluster
gcloud container clusters delete firstweek-cluster --zone=us-central1-a

# Delete static IP
gcloud compute addresses delete firstweek-ip --global

# Delete Artifact Registry
gcloud artifacts repositories delete firstweek-images --location=us-central1
```

## Support

- **Documentation**: [GKE_DEPLOYMENT_GUIDE.md](../GKE_DEPLOYMENT_GUIDE.md)
- **Quick Reference**: [QUICK_REFERENCE.md](./QUICK_REFERENCE.md)
- **GCP Console**: https://console.cloud.google.com/kubernetes
- **GKE Docs**: https://cloud.google.com/kubernetes-engine/docs

## License

See [LICENSE](../LICENSE) file in the root directory.

---

**For detailed instructions and troubleshooting, see [GKE_DEPLOYMENT_GUIDE.md](../GKE_DEPLOYMENT_GUIDE.md)**
