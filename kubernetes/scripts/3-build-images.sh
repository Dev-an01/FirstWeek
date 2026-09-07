#!/bin/bash

# ============================================================================
# Docker Image Build and Push Script - Step 3
# This script builds all Docker images and pushes them to Artifact Registry
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
REGION="us-central1"
REPO_NAME="firstweek-images"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"

# Build version tag (use git commit or timestamp)
VERSION=${1:-$(git rev-parse --short HEAD 2>/dev/null || echo "latest")}

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}firstweek - Docker Image Build${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo -e "  Registry:  ${GREEN}$REGISTRY${NC}"
echo -e "  Version:   ${GREEN}$VERSION${NC}"
echo ""

# Services to build
declare -A SERVICES=(
    ["frontend"]="./frontend"
    ["auth-service"]="./backend/auth-service"
    ["chat-service"]="./backend/chat-service"
    ["recall-service"]="./backend/recall-service"
    ["avatar-interface"]="./frontend-avatar"
    ["rag-api"]="./RAG"
)

# Function to build and push an image
build_and_push() {
    local service_name=$1
    local context_dir=$2
    local image_name="${REGISTRY}/${service_name}:${VERSION}"
    local latest_tag="${REGISTRY}/${service_name}:latest"

    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Building: ${YELLOW}$service_name${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Check if context directory exists
    if [ ! -d "$context_dir" ]; then
        echo -e "${RED}Error: Directory $context_dir does not exist${NC}"
        return 1
    fi

    # Check if Dockerfile exists
    if [ ! -f "$context_dir/Dockerfile" ]; then
        echo -e "${RED}Error: Dockerfile not found in $context_dir${NC}"
        return 1
    fi

    # Build the image
    echo -e "${YELLOW}Building image from $context_dir...${NC}"
    docker build \
        -t "$image_name" \
        -t "$latest_tag" \
        -f "$context_dir/Dockerfile" \
        "$context_dir"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Build successful${NC}"
    else
        echo -e "${RED}✗ Build failed${NC}"
        return 1
    fi

    # Push the image
    echo -e "${YELLOW}Pushing image to registry...${NC}"
    docker push "$image_name"
    docker push "$latest_tag"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Push successful${NC}"
        echo -e "${GREEN}  Image: $image_name${NC}"
        echo -e "${GREEN}  Latest: $latest_tag${NC}"
    else
        echo -e "${RED}✗ Push failed${NC}"
        return 1
    fi
}

# Build all services
FAILED_BUILDS=()

for service in "${!SERVICES[@]}"; do
    if ! build_and_push "$service" "${SERVICES[$service]}"; then
        FAILED_BUILDS+=("$service")
    fi
done

# Summary
echo -e "\n${BLUE}============================================================================${NC}"
if [ ${#FAILED_BUILDS[@]} -eq 0 ]; then
    echo -e "${GREEN}All images built and pushed successfully!${NC}"
    echo -e "${BLUE}============================================================================${NC}"
    echo ""
    echo -e "${YELLOW}Built Images:${NC}"
    for service in "${!SERVICES[@]}"; do
        echo -e "  ${GREEN}✓${NC} $service: ${REGISTRY}/${service}:${VERSION}"
    done
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo -e "  1. Update kubernetes manifests with image tags (if not using :latest)"
    echo -e "  2. Deploy secrets: ${GREEN}./kubernetes/scripts/4-deploy-secrets.sh${NC}"
    echo -e "  3. Deploy application: ${GREEN}./kubernetes/scripts/5-deploy-app.sh${NC}"
else
    echo -e "${RED}Some builds failed!${NC}"
    echo -e "${BLUE}============================================================================${NC}"
    echo ""
    echo -e "${YELLOW}Failed Builds:${NC}"
    for service in "${FAILED_BUILDS[@]}"; do
        echo -e "  ${RED}✗${NC} $service"
    done
    exit 1
fi
