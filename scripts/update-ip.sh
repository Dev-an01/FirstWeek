#!/bin/bash
# Auto-detect and update server IP in .env file
# This script runs before Docker Compose to ensure services start with correct IP

set -e

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"

echo "================================================"
echo "🔍 Auto-detecting server IP..."
echo "================================================"

# Detect public IP using GCP metadata service
get_public_ip() {
    # Try GCP metadata service first
    IP=$(curl -s -H "Metadata-Flavor: Google" \
         http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip \
         2>/dev/null)
    
    # Fallback to external IP services if GCP metadata fails
    if [ -z "$IP" ]; then
        echo "⚠️  GCP metadata not available, trying external services..."
        IP=$(curl -s https://api.ipify.org 2>/dev/null || curl -s https://ifconfig.me 2>/dev/null)
    fi
    
    echo "$IP"
}

# Get current IP
NEW_IP=$(get_public_ip)

if [ -z "$NEW_IP" ]; then
    echo "❌ Failed to detect public IP"
    echo "   Please check your network connection"
    exit 1
fi

echo "✅ Detected IP: $NEW_IP"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ .env file not found at: $ENV_FILE"
    exit 1
fi

# Read current IP from .env
CURRENT_HOST=$(grep "^HOST=" "$ENV_FILE" | cut -d'=' -f2)

if [ "$CURRENT_HOST" = "$NEW_IP" ]; then
    echo "✓  IP unchanged: $NEW_IP"
    exit 0
fi

echo "📝 Updating IP: $CURRENT_HOST → $NEW_IP"

# Update HOST and AVATAR_VIDEO_HOST in .env
sed -i.bak "s/^HOST=.*/HOST=$NEW_IP/" "$ENV_FILE"
sed -i.bak "s/^AVATAR_VIDEO_HOST=.*/AVATAR_VIDEO_HOST=$NEW_IP/" "$ENV_FILE"

echo "✅ Updated .env file"
echo "   - HOST=$NEW_IP"
echo "   - AVATAR_VIDEO_HOST=$NEW_IP"
echo "================================================"
