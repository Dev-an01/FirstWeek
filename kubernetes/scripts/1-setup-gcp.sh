#!/bin/bash

# ============================================================================
# GCP Setup Script - Step 1
# This script sets up the GCP project and enables required APIs
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
REGION="asia-northeast1"
ZONE="asia-northeast1-a"

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}firstweek - GCP Project Setup${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    echo "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

echo -e "${GREEN}✓ gcloud CLI found${NC}"

# Set project
echo -e "\n${YELLOW}Setting GCP project to: $PROJECT_ID${NC}"
gcloud config set project $PROJECT_ID

# Set default region and zone
echo -e "${YELLOW}Setting default region to: $REGION${NC}"
gcloud config set compute/region $REGION
gcloud config set compute/zone $ZONE

# Enable required APIs
echo -e "\n${BLUE}Enabling required GCP APIs...${NC}"
echo "This may take a few minutes..."

APIS=(
    "container.googleapis.com"              # GKE
    "compute.googleapis.com"                # Compute Engine
    "artifactregistry.googleapis.com"       # Artifact Registry (for Docker images)
    "cloudbuild.googleapis.com"             # Cloud Build (for CI/CD)
    "cloudresourcemanager.googleapis.com"   # Resource Manager
    "iam.googleapis.com"                    # IAM
    "secretmanager.googleapis.com"          # Secret Manager
    "servicenetworking.googleapis.com"      # Service Networking
    "sqladmin.googleapis.com"               # Cloud SQL (optional)
)

for api in "${APIS[@]}"; do
    echo -e "${YELLOW}  Enabling $api...${NC}"
    gcloud services enable $api
done

echo -e "\n${GREEN}✓ All APIs enabled successfully${NC}"

# Create Artifact Registry repository for Docker images
echo -e "\n${BLUE}Creating Artifact Registry repository...${NC}"
REPO_NAME="firstweek-images"

if gcloud artifacts repositories describe $REPO_NAME --location=$REGION &> /dev/null; then
    echo -e "${YELLOW}  Repository $REPO_NAME already exists${NC}"
else
    gcloud artifacts repositories create $REPO_NAME \
        --repository-format=docker \
        --location=$REGION \
        --description="Docker images for firstweek microservices"
    echo -e "${GREEN}✓ Artifact Registry repository created${NC}"
fi

# Configure Docker to use gcloud as credential helper
echo -e "\n${BLUE}Configuring Docker authentication...${NC}"
gcloud auth configure-docker ${REGION}-docker.pkg.dev

echo -e "\n${GREEN}✓ Docker authentication configured${NC}"

# Reserve a static IP for the Load Balancer
echo -e "\n${BLUE}Reserving global static IP address...${NC}"
IP_NAME="firstweek-ip"

if gcloud compute addresses describe $IP_NAME --global &> /dev/null; then
    echo -e "${YELLOW}  Static IP $IP_NAME already exists${NC}"
    STATIC_IP=$(gcloud compute addresses describe $IP_NAME --global --format="get(address)")
    echo -e "${GREEN}  Static IP Address: $STATIC_IP${NC}"
else
    gcloud compute addresses create $IP_NAME --global
    STATIC_IP=$(gcloud compute addresses describe $IP_NAME --global --format="get(address)")
    echo -e "${GREEN}✓ Static IP reserved: $STATIC_IP${NC}"
fi

# Create service account for GKE workloads
echo -e "\n${BLUE}Creating service account for GKE workloads...${NC}"
SA_NAME="firstweek-gke-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if gcloud iam service-accounts describe $SA_EMAIL &> /dev/null; then
    echo -e "${YELLOW}  Service account $SA_NAME already exists${NC}"
else
    gcloud iam service-accounts create $SA_NAME \
        --display-name="firstweek GKE Service Account" \
        --description="Service account for firstweek workloads running on GKE"
    echo -e "${GREEN}✓ Service account created${NC}"
fi

# Grant necessary permissions
echo -e "\n${BLUE}Granting IAM permissions to service account...${NC}"
ROLES=(
    "roles/secretmanager.secretAccessor"
    "roles/cloudsql.client"
    "roles/storage.objectViewer"
)

for role in "${ROLES[@]}"; do
    echo -e "${YELLOW}  Granting $role...${NC}"
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="$role" \
        --quiet
done

echo -e "\n${GREEN}✓ IAM permissions granted${NC}"

# Summary
echo -e "\n${BLUE}============================================================================${NC}"
echo -e "${GREEN}GCP Setup Complete!${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""
echo -e "${YELLOW}Projec  Configuration:${NC}"
echo -e "  Project ID:        ${GREEN}$PROJECT_ID${NC}"
echo -e "  Region:            ${GREEN}$REGION${NC}"
echo -e "  Zone:              ${GREEN}$ZONE${NC}"
echo -e "  Static IP:         ${GREEN}$STATIC_IP${NC}"
echo -e "  Repository:        ${GREEN}${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}${NC}"
echo -e "  Service Account:   ${GREEN}$SA_EMAIL${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "  1. Update kubernetes/base/services/*.yaml with correct image paths"
echo -e "  2. Run: ${GREEN}./kubernetes/scripts/2-create-cluster.sh${NC}"
echo ""
