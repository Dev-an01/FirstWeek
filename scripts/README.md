# Startup Scripts

This directory contains scripts for auto-detecting the server IP and starting Docker services.

## Scripts

### `update-ip.sh`
Auto-detects the server's public IP and updates `.env` file.

**Usage:**
```bash
./scripts/update-ip.sh
```

**What it does:**
1. Detects public IP using GCP metadata service
2. Falls back to external services if needed
3. Updates `HOST` in `.env`
4. Creates backup (`.env.bak`) before updating

### `start.sh`
Wrapper script that updates IP and starts Docker services.

**Usage:**
```bash
# Start with production config (default)
./scripts/start.sh

# Or specify compose file
./scripts/start.sh docker-compose.yml
```

**What it does:**
1. Runs `update-ip.sh` to update IP
2. Starts Docker services with `docker compose up -d`

## Workflow

### On Server Restart
Instead of running docker compose directly, use:
```bash
cd /home/jupyter/project-firstweek/FirstWeek
./scripts/start.sh
```

This ensures the IP is updated before services start.

### Manual IP Update Only
If you just want to update IP without restarting services:
```bash
./scripts/update-ip.sh
```

## Auto-Start on Boot (Optional)

To run automatically on server boot, add to crontab:
```bash
crontab -e
```

Add this line:
```cron
@reboot cd /home/jupyter/project-firstweek/FirstWeek && ./scripts/start.sh >> /tmp/startup.log 2>&1
```

Or wait for Docker to start first:
```cron
@reboot sleep 30 && cd /home/jupyter/project-firstweek/FirstWeek && ./scripts/start.sh >> /tmp/startup.log 2>&1
```
