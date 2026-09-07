# GKE Deployment Quick Reference

Fast reference for common operations.

## Initial Deployment (One-Time Setup)

```bash
# 0. Update project ID in all files
cd kubernetes/scripts
./0-update-project-id.sh

# 1. Setup GCP (~5 min)
./1-setup-gcp.sh

# 2. Create cluster (~10 min)
./2-create-cluster.sh

# 3. Build images (~20 min)
./3-build-images.sh

# 4. Deploy secrets (~1 min)
# First, create .env file from .env.example
cp ../../.env.example ../../.env
nano ../../.env  # Edit with your values
./4-deploy-secrets.sh

# 5. Deploy app (~15 min)
./5-deploy-app.sh

# 6. Health check (~2 min)
./6-health-check.sh
```

## Daily Operations

### Check Status

```bash
# All pods
kubectl get pods -n firstweek

# Specific service
kubectl get pods -l app=rag-api -n firstweek

# All resources
kubectl get all -n firstweek
```

### View Logs

```bash
# Real-time logs
kubectl logs -f deployment/auth-service -n firstweek

# Last 100 lines
kubectl logs --tail=100 deployment/chat-service -n firstweek

# Previous crash
kubectl logs <pod-name> -n firstweek --previous
```

### Scale Services

```bash
# Manual scale
kubectl scale deployment frontend --replicas=5 -n firstweek

# Check autoscaling
kubectl get hpa -n firstweek
```

### Restart Services

```bash
# Restart specific service
kubectl rollout restart deployment/auth-service -n firstweek

# Restart all
kubectl rollout restart deployment -n firstweek
```

### Access Services

```bash
# Port forward for local testing
kubectl port-forward svc/frontend 5173:5173 -n firstweek
kubectl port-forward svc/rag-api 8000:8000 -n firstweek

# Shell into pod
kubectl exec -it <pod-name> -n firstweek -- /bin/sh

# Database access
kubectl exec -it statefulset/avatar-user-db -n firstweek -- psql -U postgres -d avatar_user_db
```

## Updates & Rollbacks

### Deploy New Version

```bash
# Build new image
cd kubernetes/scripts
./3-build-images.sh v1.1.0

# Update deployment
kubectl set image deployment/frontend \
  frontend=us-central1-docker.pkg.dev/PROJECT_ID/firstweek-images/frontend:v1.1.0 \
  -n firstweek

# Watch rollout
kubectl rollout status deployment/frontend -n firstweek
```

### Rollback

```bash
# Rollback to previous version
kubectl rollout undo deployment/frontend -n firstweek

# Rollback to specific revision
kubectl rollout history deployment/frontend -n firstweek
kubectl rollout undo deployment/frontend --to-revision=2 -n firstweek
```

## Troubleshooting

### Pod Issues

```bash
# Describe pod
kubectl describe pod <pod-name> -n firstweek

# Events
kubectl get events -n firstweek --sort-by='.lastTimestamp' | tail -20

# Resource usage
kubectl top pods -n firstweek
kubectl top nodes
```

### Network Issues

```bash
# Test connectivity from debug pod
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n firstweek -- \
  curl http://auth-service:3001/health

# Check endpoints
kubectl get endpoints -n firstweek

# Check services
kubectl get svc -n firstweek
```

### Database Issues

```bash
# Check database pods
kubectl get pods -l app=avatar-user-db -n firstweek

# Test database connection
kubectl exec -it statefulset/avatar-user-db -n firstweek -- \
  pg_isready -U postgres -d avatar_user_db

# View database logs
kubectl logs statefulset/avatar-user-db -n firstweek
```

## Monitoring

### Resource Usage

```bash
# Current usage
kubectl top pods -n firstweek
kubectl top nodes

# Describe node
kubectl describe node <node-name>
```

### GPU Status

```bash
# GPU nodes
kubectl get nodes -l cloud.google.com/gke-accelerator

# GPU allocation
kubectl get nodes -o custom-columns=NAME:.metadata.name,GPU:.status.allocatable.'nvidia\.com/gpu'

# GPU-using pods
kubectl get pods -n firstweek -o custom-columns=NAME:.metadata.name,GPU:.spec.containers[0].resources.limits.'nvidia\.com/gpu',NODE:.spec.nodeName | grep -v "<none>"
```

## Backup & Restore

### Database Backup

```bash
# Backup user database
kubectl exec statefulset/avatar-user-db -n firstweek -- \
  pg_dump -U postgres avatar_user_db > backup-$(date +%Y%m%d).sql

# Restore
kubectl exec -i statefulset/avatar-user-db -n firstweek -- \
  psql -U postgres avatar_user_db < backup-20260110.sql
```

### Volume Snapshots

```bash
# List PVCs
kubectl get pvc -n firstweek

# Create snapshot (via GCP)
gcloud compute disks snapshot <disk-name> \
  --snapshot-names=backup-$(date +%Y%m%d) \
  --zone=us-central1-a
```

## Configuration Updates

### Update Secrets

```bash
# Edit secret
kubectl edit secret firstweek-secrets -n firstweek

# Or recreate from .env
kubectl delete secret firstweek-secrets -n firstweek
cd kubernetes/scripts
./4-deploy-secrets.sh

# Restart pods to pick up changes
kubectl rollout restart deployment -n firstweek
```

### Update ConfigMap

```bash
# Edit configmap
kubectl edit configmap firstweek-config -n firstweek

# Or apply from file
kubectl apply -f kubernetes/base/configmap.yaml

# Restart pods
kubectl rollout restart deployment -n firstweek
```

## Cluster Management

### Scale Cluster

```bash
# Scale node pool
gcloud container clusters resize firstweek-cluster \
  --node-pool default-pool \
  --num-nodes 4 \
  --zone us-central1-a

# Scale GPU pool
gcloud container clusters resize firstweek-cluster \
  --node-pool gpu-pool \
  --num-nodes 2 \
  --zone us-central1-a
```

### Upgrade Cluster

```bash
# Check available versions
gcloud container get-server-config --zone=us-central1-a

# Upgrade master
gcloud container clusters upgrade firstweek-cluster \
  --master \
  --cluster-version=1.28.5-gke.1000 \
  --zone=us-central1-a

# Upgrade nodes
gcloud container clusters upgrade firstweek-cluster \
  --node-pool=default-pool \
  --zone=us-central1-a
```

## Cost Management

### Check Costs

```bash
# View current resource usage
gcloud compute instances list
gcloud compute disks list

# Estimate costs
# Visit: https://cloud.google.com/products/calculator
```

### Reduce Costs

```bash
# Scale down during off-hours
kubectl scale deployment --all --replicas=1 -n firstweek

# Use preemptible nodes (non-prod)
gcloud container node-pools create preemptible-pool \
  --cluster=firstweek-cluster \
  --preemptible \
  --machine-type=n1-standard-4 \
  --num-nodes=2 \
  --zone=us-central1-a
```

## Cleanup

### Delete Specific Resources

```bash
# Delete a deployment
kubectl delete deployment frontend -n firstweek

# Delete all deployments
kubectl delete deployment --all -n firstweek

# Delete namespace (deletes everything in it)
kubectl delete namespace firstweek
```

### Delete Entire Cluster

```bash
# Delete cluster (⚠️ irreversible)
gcloud container clusters delete firstweek-cluster --zone=us-central1-a

# Delete static IP
gcloud compute addresses delete firstweek-ip --global

# Delete Artifact Registry
gcloud artifacts repositories delete firstweek-images --location=us-central1
```

## Useful Aliases

Add to `~/.bashrc` or `~/.zshrc`:

```bash
alias k='kubectl'
alias kga='kubectl get all -n firstweek'
alias kgp='kubectl get pods -n firstweek'
alias kgs='kubectl get svc -n firstweek'
alias kl='kubectl logs -f -n firstweek'
alias kd='kubectl describe -n firstweek'
alias ke='kubectl exec -it -n firstweek'
alias kpf='kubectl port-forward -n firstweek'
```

## Emergency Procedures

### All Pods Crashing

```bash
# 1. Check events
kubectl get events -n firstweek --sort-by='.lastTimestamp'

# 2. Check logs of crashing pods
kubectl logs <pod-name> -n firstweek --previous

# 3. Check secrets
kubectl get secret firstweek-secrets -n firstweek

# 4. Rollback if recent deployment
kubectl rollout undo deployment --all -n firstweek
```

### Out of Resources

```bash
# 1. Check node resources
kubectl describe nodes | grep -A 5 "Allocated resources"

# 2. Scale up cluster
gcloud container clusters resize firstweek-cluster \
  --node-pool default-pool \
  --num-nodes 4 \
  --zone us-central1-a

# 3. Or reduce pod replicas temporarily
kubectl scale deployment --all --replicas=1 -n firstweek
```

### Database Corruption

```bash
# 1. Stop services using the database
kubectl scale deployment auth-service chat-service --replicas=0 -n firstweek

# 2. Backup current state
kubectl exec statefulset/avatar-user-db -n firstweek -- \
  pg_dump -U postgres avatar_user_db > emergency-backup-$(date +%Y%m%d-%H%M%S).sql

# 3. Restore from good backup
kubectl exec -i statefulset/avatar-user-db -n firstweek -- \
  psql -U postgres avatar_user_db < good-backup.sql

# 4. Restart services
kubectl scale deployment auth-service chat-service --replicas=2 -n firstweek
```

## Support Resources

- **GKE Documentation**: https://cloud.google.com/kubernetes-engine/docs
- **Kubectl Cheat Sheet**: https://kubernetes.io/docs/reference/kubectl/cheatsheet/
- **GCP Console**: https://console.cloud.google.com/kubernetes
- **GCP Status**: https://status.cloud.google.com/

---

**Keep this file handy for quick reference during operations!**
