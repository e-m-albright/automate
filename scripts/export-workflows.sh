#!/usr/bin/env bash
# export-workflows.sh — Export all n8n workflows as version-controlled JSON
#
# Pulls workflows from the n8n API, strips sensitive/ephemeral fields
# (credentials IDs, owner metadata, execution data), and writes clean
# JSON files to n8n/workflows/.
#
# Usage: ./scripts/export-workflows.sh
# Requires: curl, jq, a running n8n instance at N8N_URL

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load .env if N8N_API_KEY isn't already in the environment
if [ -z "${N8N_API_KEY:-}" ] && [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$PROJECT_DIR/.env"
  set +a
fi

N8N_URL="${N8N_URL:-http://localhost:5678}"
API_URL="${N8N_URL}/api/v1"
OUT_DIR="${PROJECT_DIR}/n8n/workflows"

mkdir -p "$OUT_DIR"

# Fetch API key from environment or prompt
if [ -z "${N8N_API_KEY:-}" ]; then
  echo "Error: N8N_API_KEY is not set."
  echo "Generate one at ${N8N_URL}/settings/api"
  exit 1
fi

AUTH_HEADER="X-N8N-API-KEY: ${N8N_API_KEY}"

echo "Fetching workflow list from ${API_URL}..."
WORKFLOWS=$(curl -sf -H "$AUTH_HEADER" "${API_URL}/workflows?limit=250")

if [ -z "$WORKFLOWS" ]; then
  echo "Error: Could not fetch workflows. Is n8n running?"
  exit 1
fi

COUNT=$(echo "$WORKFLOWS" | jq '.data | length')
echo "Found ${COUNT} workflow(s)."

echo "$WORKFLOWS" | jq -r '.data[] | .id' | while read -r WF_ID; do
  # Fetch full workflow
  WF_JSON=$(curl -sf -H "$AUTH_HEADER" "${API_URL}/workflows/${WF_ID}")

  # Extract name for filename
  WF_NAME=$(echo "$WF_JSON" | jq -r '.name')

  # Create a safe filename: lowercase, replace non-alphanumeric with dashes
  SAFE_NAME=$(echo "$WF_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
  FILENAME="${SAFE_NAME}.json"

  # Strip sensitive and ephemeral fields, keep the workflow definition
  echo "$WF_JSON" | jq '{
    id: .id,
    name: .name,
    active: .active,
    nodes: [.nodes[] | del(.credentials)],
    connections: .connections,
    settings: .settings,
    pinData: .pinData,
    meta: .meta,
    tags: [.tags[]? | {name: .name}]
  }' > "${OUT_DIR}/${FILENAME}"

  echo "  Exported: ${FILENAME}"
done

echo ""
echo "Done. ${COUNT} workflow(s) exported to ${OUT_DIR}/"
echo ""
echo "Review with: git diff n8n/workflows/"
