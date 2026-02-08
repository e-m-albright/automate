#!/bin/bash
set -e

echo "=== Automate Setup ==="
echo ""

# Check for just
if ! command -v just &> /dev/null; then
    echo "NOTE: 'just' is recommended. Install: brew install just (or cargo install just)"
    echo "      For now, running setup directly."
fi

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is required. Install from https://docker.com"
    exit 1
fi

if ! command -v docker compose &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "ERROR: Docker Compose is required."
    exit 1
fi

# Copy .env if needed
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example — edit as needed."
fi

echo ""
echo "Starting services..."
docker compose up -d

echo ""
echo "Waiting for Ollama to be ready..."
sleep 5

echo "Pulling models..."
# Load model selection from .env (defaults used if unset)
set -a
source .env 2>/dev/null || true
set +a
docker exec automate-ollama ollama pull "${OLLAMA_SETUP_LOCAL_MODEL:-gemma3:latest}"
if [ -n "${OLLAMA_SETUP_CLOUD_MODEL:-}" ]; then
    docker exec automate-ollama ollama signin
    docker exec automate-ollama ollama pull "$OLLAMA_SETUP_CLOUD_MODEL"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Services:"
echo "  n8n:    http://localhost:5678"
echo "  Ollama: http://localhost:11434"
echo ""
echo "Quick commands (use 'just --list' to see all):"
echo "  just up          start services"
echo "  just open        open n8n in browser"
echo "  just status      check everything"
