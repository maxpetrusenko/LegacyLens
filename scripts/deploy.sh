#!/usr/bin/env bash
set -euo pipefail

if ! command -v railway >/dev/null 2>&1; then
  echo "railway CLI not found. Install with: npm i -g @railway/cli"
  exit 1
fi

APP_URL="${APP_URL:-}"
if [[ -z "${APP_URL}" ]]; then
  echo "APP_URL is required (example: https://legacylens-production.up.railway.app)"
  exit 1
fi

echo "1) Deploying current commit to Railway..."
railway up

echo "2) Running health check..."
curl --fail --silent --show-error "${APP_URL}/health" >/dev/null

echo "3) Running smoke query..."
curl --fail --silent --show-error \
  -X POST "${APP_URL}/query" \
  -H "content-type: application/json" \
  -d '{"query":"Where is STOP RUN used?"}' >/dev/null

echo "Deployment verification passed."
