#!/bin/bash

# ============================================================================
# Secrets Deployment Script - Step 4
# This script creates Kubernetes secrets from your .env file
# ============================================================================

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NAMESPACE="firstweek"
SECRET_NAME="firstweek-secrets"
ENV_FILE="../.env"

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}firstweek - Secrets Deployment${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}Error: .env file not found at $ENV_FILE${NC}"
    echo -e "${YELLOW}Please create a .env file with all required secrets${NC}"
    echo -e "${YELLOW}You can copy from .env.example as a starting point${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found .env file${NC}"

# Check if kubectl is configured
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}Error: kubectl is not configured or cluster is not accessible${NC}"
    echo -e "${YELLOW}Please run: gcloud container clusters get-credentials [CLUSTER_NAME] --zone=[ZONE]${NC}"
    exit 1
fi

echo -e "${GREEN}✓ kubectl is configured${NC}"

# Create namespace if it doesn't exist
if kubectl get namespace $NAMESPACE &> /dev/null; then
    echo -e "${YELLOW}Namespace $NAMESPACE already exists${NC}"
else
    echo -e "${BLUE}Creating namespace: $NAMESPACE${NC}"
    kubectl create namespace $NAMESPACE
    echo -e "${GREEN}✓ Namespace created${NC}"
fi

# Check if secret already exists
if kubectl get secret $SECRET_NAME -n $NAMESPACE &> /dev/null; then
    echo -e "${YELLOW}Secret $SECRET_NAME already exists in namespace $NAMESPACE${NC}"
    read -p "Do you want to delete and recreate it? (yes/no): " RECREATE
    if [ "$RECREATE" == "yes" ]; then
        kubectl delete secret $SECRET_NAME -n $NAMESPACE
        echo -e "${GREEN}✓ Existing secret deleted${NC}"
    else
        echo -e "${YELLOW}Skipping secret creation${NC}"
        exit 0
    fi
fi

# Create secret from .env file
echo -e "\n${BLUE}Creating Kubernetes secret from .env file...${NC}"

kubectl create secret generic $SECRET_NAME \
    --from-env-file=$ENV_FILE \
    --namespace=$NAMESPACE

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Secret created successfully${NC}"
else
    echo -e "${RED}✗ Failed to create secret${NC}"
    exit 1
fi

# Verify secret
echo -e "\n${BLUE}Verifying secret...${NC}"
SECRET_KEYS=$(kubectl get secret $SECRET_NAME -n $NAMESPACE -o jsonpath='{.data}' | jq -r 'keys[]' | wc -l)
echo -e "${GREEN}✓ Secret contains $SECRET_KEYS keys${NC}"

# Show secret keys (not values)
echo -e "\n${YELLOW}Secret keys:${NC}"
kubectl get secret $SECRET_NAME -n $NAMESPACE -o jsonpath='{.data}' | jq -r 'keys[]' | sed 's/^/  - /'

# Warning about sensitive data
echo -e "\n${YELLOW}⚠️  SECURITY REMINDER:${NC}"
echo -e "${YELLOW}  - Never commit .env file to git${NC}"
echo -e "${YELLOW}  - Store secrets securely (use Google Secret Manager for production)${NC}"
echo -e "${YELLOW}  - Rotate secrets regularly${NC}"
echo -e "${YELLOW}  - Use RBAC to restrict secret access${NC}"

# Summary
echo -e "\n${BLUE}============================================================================${NC}"
echo -e "${GREEN}Secrets Deployment Complete!${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "  1. Deploy ConfigMap: ${GREEN}kubectl apply -f kubernetes/base/configmap.yaml${NC}"
echo -e "  2. Deploy application: ${GREEN}./kubernetes/scripts/5-deploy-app.sh${NC}"
echo ""
