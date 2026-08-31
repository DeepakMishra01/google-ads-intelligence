#!/usr/bin/env bash
# One-command redeploy on the EC2 host: pull the latest code, rebuild the image,
# and recreate the container (so the new --env-file / code takes effect).
#
# Usage (on the server):   ./update.sh
set -euo pipefail

cd "$(dirname "$0")"

echo "[update] pulling latest code..."
git pull --ff-only

echo "[update] building image (a few minutes on t3.micro)..."
docker build -t kapp-ads:latest .

echo "[update] recreating container..."
docker rm -f kapp-ads 2>/dev/null || true
docker run -d --name kapp-ads \
  --env-file "$(pwd)/.env" \
  -p 127.0.0.1:8000:8000 \
  --restart unless-stopped \
  kapp-ads:latest

sleep 3
echo "[update] health:"
curl -s http://127.0.0.1:8000/api/v1/health || true
echo
echo "[update] done."
