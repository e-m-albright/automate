# ============================================================================
# Automate — n8n + Ollama
# ============================================================================
#
# n8n is the main app — build workflows at http://localhost:5678
# Ollama provides local LLM for workflows (http://localhost:11434).
#
# Usage:  just <recipe>
#         just --list
#
# Requires: docker, just
# ============================================================================

set dotenv-load := true
set shell := ["bash", "-euo", "pipefail", "-c"]

default_model := "qwen2.5:7b"

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

# First-time project setup — create .env, start services
setup:
    @if [ ! -f .env ]; then \
        cp .env.example .env; \
        echo "▸ Created .env from .env.example — edit as needed."; \
    fi
    @echo ""
    @echo "✓ Setup complete. Next:"
    @echo "  just up          start n8n + ollama"
    @echo "  just pull-model  download the local LLM"
    @echo "  just open        open n8n in your browser"

# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------

# Start OrbStack (Docker runtime)
orbstack-up:
    orbctl start

# Start everything (n8n + Ollama)
up *args:
    docker compose up -d {{args}}

# Stop everything
down:
    docker compose down

# Restart everything
restart:
    docker compose restart

# Open n8n in your browser
open:
    @echo "Opening n8n at http://localhost:5678..."
    @open http://localhost:5678 2>/dev/null || xdg-open http://localhost:5678

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

# Show logs (follow mode) — all services or specify one
logs *args:
    docker compose logs -f {{args}}

# Show logs for a specific service
log service:
    docker compose logs -f {{service}}

# Full nuke and rebuild (keeps volumes)
rebuild-all:
    docker compose down
    docker compose build --no-cache
    docker compose up -d

# ---------------------------------------------------------------------------
# Ollama / Local LLM
# ---------------------------------------------------------------------------

# Pull the default local model
pull-model model=default_model:
    docker exec automate-ollama ollama pull {{model}}

# Pull the vision model for future use
pull-vision:
    docker exec automate-ollama ollama pull qwen2.5-vl:7b

# List downloaded models
models:
    docker exec automate-ollama ollama list

# Chat with the local model (interactive)
chat model=default_model:
    docker exec -it automate-ollama ollama run {{model}}

# ---------------------------------------------------------------------------
# n8n Workflow Version Control
# ---------------------------------------------------------------------------

# Export all n8n workflows as JSON to n8n/workflows/
export-workflows:
    @scripts/export-workflows.sh

# Import workflow JSON files from n8n/workflows/ into n8n
import-workflows:
    @scripts/import-workflows.sh

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

# Show project structure
tree:
    @find . -type f \
        -not -path './.git/*' \
        -not -path './.venv/*' \
        -not -path './node_modules/*' \
        -not -name '.DS_Store' \
        | sort

# Show status of all services
status:
    @echo "▸ Docker containers:"
    @docker compose ps 2>/dev/null || echo "  (not running)"
    @echo ""
    @echo "▸ n8n:    http://localhost:5678"
    @echo "▸ Ollama: http://localhost:11434"
    @echo ""
    @echo "▸ Ollama models:"
    @docker exec automate-ollama ollama list 2>/dev/null || echo "  (not running)"
