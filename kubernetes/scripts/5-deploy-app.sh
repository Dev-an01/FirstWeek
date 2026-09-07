#!/bin/bash

# ============================================================================
# Application Deployment Script - Step 5
# This script deploys all Kubernetes resources
# ============================================================================

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NAMESPACE="firstweek"
K8S_BASE="kubernetes/base"

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}firstweek - Application Deployment${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# Check if kubectl is configured
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}Error: kubectl is not configured or cluster is not accessible${NC}"
    exit 1
fi

echo -e "${GREEN}✓ kubectl is configured${NC}"

# Function to apply manifests with status
apply_manifest() {
    local file=$1
    local description=$2

    echo -e "\n${BLUE}Deploying: ${YELLOW}$description${NC}"
    if kubectl apply -f "$file"; then
        echo -e "${GREEN}✓ $description deployed${NC}"
    else
        echo -e "${RED}✗ Failed to deploy $description${NC}"
        return 1
    fi
}

# Step 1: Create namespace
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 1: Namespace${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
apply_manifest "$K8S_BASE/namespace.yaml" "Namespace"

# Step 2: ConfigMap
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 2: ConfigMap${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
apply_manifest "$K8S_BASE/configmap.yaml" "ConfigMap"

# Step 3: Databases
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 3: Databases${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

apply_manifest "$K8S_BASE/databases/avatar-user-db.yaml" "PostgreSQL User Database"
apply_manifest "$K8S_BASE/databases/rag-postgres.yaml" "PostgreSQL RAG Database"
apply_manifest "$K8S_BASE/databases/neo4j.yaml" "Neo4j Graph Database"
apply_manifest "$K8S_BASE/databases/redis.yaml" "Redis Cache"

echo -e "\n${YELLOW}Waiting for databases to be ready (this may take 2-3 minutes)...${NC}"
kubectl wait --for=condition=ready pod -l app=avatar-user-db -n $NAMESPACE --timeout=300s
kubectl wait --for=condition=ready pod -l app=rag-postgres -n $NAMESPACE --timeout=300s
kubectl wait --for=condition=ready pod -l app=neo4j -n $NAMESPACE --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis -n $NAMESPACE --timeout=300s
echo -e "${GREEN}✓ All databases are ready${NC}"

# Step 4: Backend Services
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 4: Backend Services${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

apply_manifest "$K8S_BASE/services/auth-service.yaml" "Auth Service"
apply_manifest "$K8S_BASE/services/chat-service.yaml" "Chat Service"
apply_manifest "$K8S_BASE/services/recall-service.yaml" "Recall Service"
apply_manifest "$K8S_BASE/services/avatar-interface.yaml" "Avatar Interface"

# Step 5: RAG API (GPU workload)
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 5: RAG API (GPU Service)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

apply_manifest "$K8S_BASE/services/rag-api.yaml" "RAG API"

echo -e "\n${YELLOW}Waiting for RAG API to be ready (this may take 5-10 minutes for model downloads)...${NC}"
kubectl wait --for=condition=ready pod -l app=rag-api -n $NAMESPACE --timeout=600s
echo -e "${GREEN}✓ RAG API is ready${NC}"

# Step 6: Frontend
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 6: Frontend${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

apply_manifest "$K8S_BASE/services/frontend.yaml" "Frontend"

# Step 7: Horizontal Pod Autoscalers
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 7: Autoscaling${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

apply_manifest "$K8S_BASE/hpa.yaml" "Horizontal Pod Autoscalers"

# Step 8: Ingress (optional - requires domain setup)
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 8: Ingress (Optional)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

read -p "Do you want to deploy Ingress? (requires domain setup) (yes/no): " DEPLOY_INGRESS
if [ "$DEPLOY_INGRESS" == "yes" ]; then
    apply_manifest "$K8S_BASE/ingress.yaml" "Ingress"
    echo -e "${YELLOW}Note: SSL certificate provisioning may take 10-15 minutes${NC}"
else
    echo -e "${YELLOW}Skipping Ingress deployment${NC}"
fi

# Verification
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Deployment Verification${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "\n${YELLOW}All Pods:${NC}"
kubectl get pods -n $NAMESPACE -o wide

echo -e "\n${YELLOW}All Services:${NC}"
kubectl get services -n $NAMESPACE

echo -e "\n${YELLOW}Persistent Volume Claims:${NC}"
kubectl get pvc -n $NAMESPACE

echo -e "\n${YELLOW}Horizontal Pod Autoscalers:${NC}"
kubectl get hpa -n $NAMESPACE

# Summary
echo -e "\n${BLUE}============================================================================${NC}"
echo -e "${GREEN}Application Deployment Complete!${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "  1. Check pod status: ${GREEN}kubectl get pods -n $NAMESPACE${NC}"
echo -e "  2. View logs: ${GREEN}kubectl logs -f deployment/[service-name] -n $NAMESPACE${NC}"
echo -e "  3. Port-forward for testing: ${GREEN}kubectl port-forward svc/frontend 5173:5173 -n $NAMESPACE${NC}"
echo -e "  4. Monitor resources: ${GREEN}kubectl top pods -n $NAMESPACE${NC}"
echo ""
echo -e "${YELLOW}Useful Commands:${NC}"
echo -e "  Scale deployment: ${GREEN}kubectl scale deployment [name] --replicas=3 -n $NAMESPACE${NC}"
echo -e "  Restart deployment: ${GREEN}kubectl rollout restart deployment/[name] -n $NAMESPACE${NC}"
echo -e "  View events: ${GREEN}kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp'${NC}"
echo ""
