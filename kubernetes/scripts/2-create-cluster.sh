#!/bin/bash

# ============================================================================
# GKE Cluster Creation Script - Step 2
# This script creates a GKE cluster with GPU support
# ============================================================================

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration 
PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID to your cloud project}"
CLUSTER_NAME="firstweek-cluster"
REGION="asia-northeast1" 
ZONE="asia-northeast1-a"

# Node pool configuration
STANDARD_MACHINE_TYPE="n4-standard-4"
STANDARD_MIN_NODES=1                    # Start with 1 node (cost-optimized)
STANDARD_MAX_NODES=8                    # Scale to 3 under load

GPU_MACHINE_TYPE="a2-highgpu-1g"
GPU_ACCELERATOR="nvidia-a100"
GPU_MIN_NODES=1
GPU_MAX_NODES=1

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}firstweek - GKE Cluster Creation${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# Check if cluster already exists
if gcloud container clusters describe $CLUSTER_NAME --zone=$ZONE &> /dev/null; then
    echo -e "${YELLOW}Cluster $CLUSTER_NAME already exists in zone $ZONE${NC}"
    read -p "Do you want to delete and recreate it? (yes/no): " RECREATE
    if [ "$RECREATE" == "yes" ]; then
        echo -e "${YELLOW}Deleting existing cluster...${NC}"
        gcloud container clusters delete $CLUSTER_NAME --zone=$ZONE --quiet
        echo -e "${GREEN}✓ Cluster deleted${NC}"
    else
        echo -e "${YELLOW}Skipping cluster creation${NC}"
        exit 0
    fi
fi

# Create GKE cluster
echo -e "\n${BLUE}Creating GKE cluster: $CLUSTER_NAME${NC}"
echo -e "${YELLOW}This will take approximately 5-10 minutes...${NC}"

gcloud container clusters create $CLUSTER_NAME \
    --zone=$ZONE \
    --machine-type=$STANDARD_MACHINE_TYPE \
    --num-nodes=$STANDARD_MIN_NODES \
    --enable-autoscaling \
    --min-nodes=$STANDARD_MIN_NODES \
    --max-nodes=$STANDARD_MAX_NODES \
    --enable-autorepair \
    --enable-autoupgrade \
    --enable-ip-alias \
    --network="default" \
    --subnetwork="default" \
    --no-enable-basic-auth \
    --no-issue-client-certificate \
    --enable-stackdriver-kubernetes \
    --addons=HorizontalPodAutoscaling,HttpLoadBalancing,GcePersistentDiskCsiDriver \
    --workload-pool=${PROJECT_ID}.svc.id.goog \
    --release-channel=regular

echo -e "\n${GREEN}✓ GKE cluster created successfully${NC}"

# Get cluster credentials
echo -e "\n${BLUE}Getting cluster credentials...${NC}"
gcloud container clusters get-credentials $CLUSTER_NAME --zone=$ZONE

echo -e "${GREEN}✓ Credentials configured${NC}"

# Add GPU node pool
echo -e "\n${BLUE}Creating GPU node pool for RAG service...${NC}"
echo -e "${YELLOW}This will take approximately 3-5 minutes...${NC}"

gcloud container node-pools create gpu-pool \
    --cluster=$CLUSTER_NAME \
    --zone=$ZONE \
    --machine-type=$GPU_MACHINE_TYPE \
    --accelerator=type=$GPU_ACCELERATOR,count=1 \
    --num-nodes=$GPU_MIN_NODES \
    --enable-autoscaling \
    --min-nodes=$GPU_MIN_NODES \
    --max-nodes=$GPU_MAX_NODES \
    --enable-autorepair \
    --enable-autoupgrade

echo -e "\n${GREEN}✓ GPU node pool created${NC}"

# Install NVIDIA GPU device drivers
echo -e "\n${BLUE}Installing NVIDIA GPU drivers on GKE...${NC}"

kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/master/nvidia-driver-installer/cos/daemonset-preloaded-latest.yaml

echo -e "${GREEN}✓ GPU drivers installed${NC}"

# Verify cluster
echo -e "\n${BLUE}Verifying cluster setup...${NC}"

echo -e "\n${YELLOW}Cluster Info:${NC}"
gcloud container clusters describe $CLUSTER_NAME --zone=$ZONE --format="table(name,status,currentMasterVersion,currentNodeCount,location)"

echo -e "\n${YELLOW}Node Pools:${NC}"
gcloud container node-pools list --cluster=$CLUSTER_NAME --zone=$ZONE --format="table(name,machineType,autoscaling.enabled,initialNodeCount)"

echo -e "\n${YELLOW}Nodes:${NC}"
kubectl get nodes -o wide

echo -e "\n${YELLOW}GPU Resources:${NC}"
kubectl get nodes -o custom-columns=NAME:.metadata.name,GPU:.status.allocatable.'nvidia\.com/gpu'

# Summary
echo -e "\n${BLUE}============================================================================${NC}"
echo -e "${GREEN}GKE Cluster Creation Complete!${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""
echo -e "${YELLOW}Cluster Configuration:${NC}"
echo -e "  Cluster Name:      ${GREEN}$CLUSTER_NAME${NC}"
echo -e "  Zone:              ${GREEN}$ZONE${NC}"
echo -e "  Standard Nodes:    ${GREEN}$STANDARD_MIN_NODES-$STANDARD_MAX_NODES (autoscaling)${NC}"
echo -e "  GPU Nodes:         ${GREEN}$GPU_MIN_NODES-$GPU_MAX_NODES (autoscaling)${NC}"
echo -e "  GPU Type:          ${GREEN}$GPU_ACCELERATOR${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "  1. Build and push Docker images: ${GREEN}./kubernetes/scripts/3-build-images.sh${NC}"
echo -e "  2. Deploy secrets: ${GREEN}./kubernetes/scripts/4-deploy-secrets.sh${NC}"
echo -e "  3. Deploy application: ${GREEN}./kubernetes/scripts/5-deploy-app.sh${NC}"
echo ""
