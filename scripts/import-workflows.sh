#!/usr/bin/env bash
# import-workflows.sh — Import workflow JSON files from n8n/workflows/ into n8n
#
# Reads each .json file in n8n/workflows/, strips the stored id so n8n
# creates new workflows, and POSTs to the n8n API.
#
# Usage: ./scripts/import-workflows.sh [dir]
#   dir  Optional. Default: project n8n/workflows/
# Requires: curl, jq, a running n8n instance at N8N_URL

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
IN_DIR="${1:-${PROJECT_DIR}/n8n/workflows}"

# Load .env if N8N_API_KEY isn't already in the environment
if [ -z "${N8N_API_KEY:-}" ] && [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$PROJECT_DIR/.env"
  set +a
fi

N8N_URL="${N8N_URL:-http://localhost:5678}"
API_URL="${N8N_URL}/api/v1"

if [ ! -d "$IN_DIR" ]; then
  echo "Error: Directory not found: ${IN_DIR}"
  exit 1
fi

if [ -z "${N8N_API_KEY:-}" ]; then
  echo "Error: N8N_API_KEY is not set."
  echo "Generate one at ${N8N_URL}/settings/api"
  exit 1
fi

AUTH_HEADER="X-N8N-API-KEY: ${N8N_API_KEY}"

# Check n8n is reachable
if ! curl -sf -H "$AUTH_HEADER" "${API_URL}/workflows?limit=1" >/dev/null; then
  echo "Error: Could not reach n8n at ${N8N_URL}. Is it running?"
  exit 1
fi

COUNT=0
for f in "$IN_DIR"/*.json; do
  [ -f "$f" ] || continue
  BASENAME=$(basename "$f" .json)
  # API requires settings but rejects extra keys (e.g. executionOrder, binaryMode); send empty object
  PAYLOAD=$(jq '
    {
      name: (.name // "Unnamed"),
      nodes: [.nodes[]? | del(.credentials)],
      connections: (.connections // {}),
      settings: {}
    }
  ' "$f")
  RESP=$(curl -s -w "\n%{http_code}" -X POST -H "$AUTH_HEADER" -H "Content-Type: application/json" \
    -d "$PAYLOAD" "${API_URL}/workflows")
  HTTP_CODE=$(echo "$RESP" | tail -n1)
  BODY=$(echo "$RESP" | sed '$d')
  if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    NEW_ID=$(echo "$BODY" | jq -r '.id')
    NEW_NAME=$(echo "$BODY" | jq -r '.name')
    echo "  Imported: ${BASENAME}.json → ${NEW_NAME} (id: ${NEW_ID})"
    COUNT=$((COUNT + 1))
  else
    echo "Error: n8n returned HTTP ${HTTP_CODE} for ${BASENAME}.json"
    echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
    exit 1
  fi
done

echo ""
echo "Done. ${COUNT} workflow(s) imported from ${IN_DIR}/"
echo ""
