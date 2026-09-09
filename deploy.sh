#!/bin/bash
# Pull the latest code and rebuild the running container.
# Usage (on the VM): cd ~/cyber_discord_bot && ./deploy.sh
set -euo pipefail

cd "$(dirname "$0")"

echo "==> Pulling latest changes"
git pull

echo "==> Rebuilding and restarting the bot container"
docker compose up -d --build

echo "==> Recent logs"
docker compose logs --tail 15
