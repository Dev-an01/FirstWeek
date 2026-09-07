#!/bin/bash
# Startup script for Docker Compose with auto-IP detection
# Usage: ./scripts/start.sh [compose-file]

set -e

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="${1:-docker-compose.prod.yml}"

cd "$PROJECT_DIR"

# Step 1: Update IP in .env
echo "Step 1: Updating server IP..."
bash "$SCRIPT_DIR/update-ip.sh"

# Step 2: Start Docker services
echo ""
echo "Step 2: Starting Docker services..."
docker compose -f "$COMPOSE_FILE" up -d

echo ""
echo "✅ All services started successfully!"
echo "   Use 'docker compose -f $COMPOSE_FILE logs -f' to view logs"
