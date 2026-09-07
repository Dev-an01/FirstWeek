#!/bin/bash

# ============================================================================
# Health Check Script - Step 6
# This script verifies all services are healthy
# ============================================================================

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NAMESPACE="firstweek"

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}firstweek - Health Check${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# Check if kubectl is configured
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}Error: kubectl is not configured or cluster is not accessible${NC}"
    exit 1
fi

# Function to check pod status
check_pods() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Pod Status${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    local all_running=true
    local services=("avatar-user-db" "rag-postgres" "neo4j" "redis" "auth-service" "chat-service" "recall-service" "avatar-interface" "rag-api" "frontend")

    for service in "${services[@]}"; do
        local status=$(kubectl get pods -n $NAMESPACE -l app=$service -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
        local ready=$(kubectl get pods -n $NAMESPACE -l app=$service -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)

        if [ "$status" == "Running" ] && [ "$ready" == "True" ]; then
            echo -e "  ${GREEN}✓${NC} $service: ${GREEN}Running & Ready${NC}"
        elif [ "$status" == "Running" ]; then
            echo -e "  ${YELLOW}⚠${NC} $service: ${YELLOW}Running but not ready${NC}"
            all_running=false
        else
            echo -e "  ${RED}✗${NC} $service: ${RED}$status${NC}"
            all_running=false
        fi
    done

    return $([ "$all_running" == "true" ] && echo 0 || echo 1)
}

# Function to check service endpoints
check_services() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Service Endpoints${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    kubectl get services -n $NAMESPACE -o custom-columns=NAME:.metadata.name,TYPE:.spec.type,CLUSTER-IP:.spec.clusterIP,PORT:.spec.ports[0].port
}

# Function to check PVCs
check_storage() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Persistent Storage${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    local all_bound=true
    local pvcs=$(kubectl get pvc -n $NAMESPACE -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.phase}{"\n"}{end}')

    while IFS= read -r line; do
        local name=$(echo $line | awk '{print $1}')
        local status=$(echo $line | awk '{print $2}')

        if [ "$status" == "Bound" ]; then
            echo -e "  ${GREEN}✓${NC} $name: ${GREEN}$status${NC}"
        else
            echo -e "  ${RED}✗${NC} $name: ${RED}$status${NC}"
            all_bound=false
        fi
    done <<< "$pvcs"

    return $([ "$all_bound" == "true" ] && echo 0 || echo 1)
}

# Function to check resource usage
check_resources() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Resource Usage${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    echo -e "\n${YELLOW}Pod Resource Usage:${NC}"
    kubectl top pods -n $NAMESPACE 2>/dev/null || echo -e "${YELLOW}Metrics not available yet (metrics-server may still be initializing)${NC}"

    echo -e "\n${YELLOW}Node Resource Usage:${NC}"
    kubectl top nodes 2>/dev/null || echo -e "${YELLOW}Metrics not available yet${NC}"
}

# Function to check GPU allocation
check_gpu() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}GPU Allocation${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    echo -e "\n${YELLOW}GPU Nodes:${NC}"
    kubectl get nodes -l cloud.google.com/gke-accelerator -o custom-columns=NAME:.metadata.name,GPU:.status.allocatable.'nvidia\.com/gpu',STATUS:.status.conditions[-1].type

    echo -e "\n${YELLOW}GPU-using Pods:${NC}"
    kubectl get pods -n $NAMESPACE -o custom-columns=NAME:.metadata.name,GPU:.spec.containers[0].resources.limits.'nvidia\.com/gpu',NODE:.spec.nodeName | grep -v "<none>" || echo "No GPU pods found"
}

# Function to check recent events
check_events() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Recent Events (Last 10)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp' | tail -10
}

# Function to check ingress
check_ingress() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Ingress Configuration${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if kubectl get ingress -n $NAMESPACE &> /dev/null; then
        kubectl get ingress -n $NAMESPACE -o wide
    else
        echo -e "${YELLOW}No Ingress configured${NC}"
    fi
}

# Run all checks
check_pods
PODS_OK=$?

check_services

check_storage
STORAGE_OK=$?

check_resources

check_gpu

check_events

check_ingress

# Summary
echo -e "\n${BLUE}============================================================================${NC}"
if [ $PODS_OK -eq 0 ] && [ $STORAGE_OK -eq 0 ]; then
    echo -e "${GREEN}Health Check: ALL SYSTEMS OPERATIONAL ✓${NC}"
else
    echo -e "${YELLOW}Health Check: SOME ISSUES DETECTED ⚠${NC}"
fi
echo -e "${BLUE}============================================================================${NC}"
echo ""
echo -e "${YELLOW}Troubleshooting Commands:${NC}"
echo -e "  Check pod logs: ${GREEN}kubectl logs -f deployment/[service-name] -n $NAMESPACE${NC}"
echo -e "  Describe pod: ${GREEN}kubectl describe pod [pod-name] -n $NAMESPACE${NC}"
echo -e "  Get events: ${GREEN}kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp'${NC}"
echo -e "  Shell into pod: ${GREEN}kubectl exec -it [pod-name] -n $NAMESPACE -- /bin/sh${NC}"
echo ""
