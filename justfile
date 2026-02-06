# ============================================================================
# Automate — n8n + privacy-first LLM sidecar
# ============================================================================
#
# n8n is the main app — build workflows at http://localhost:5678
# The sidecar handles bookmark parsing & LLM privacy routing.
#
# Usage:  just <recipe>
#         just --list
#
# Requires: uv, docker, just
# ============================================================================

set dotenv-load := true
set shell := ["bash", "-euo", "pipefail", "-c"]

default_model := "qwen2.5:7b"

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

# First-time project setup — install deps, create .env
setup: _ensure-uv
    @echo "▸ Installing Python dependencies..."
    uv sync --all-extras
    @if [ ! -f .env ]; then \
        cp .env.example .env; \
        echo "▸ Created .env from .env.example — edit it with your API keys."; \
    fi
    @echo ""
    @echo "✓ Setup complete. Next:"
    @echo "  just up          start n8n + sidecar + ollama"
    @echo "  just pull-model  download the local LLM"
    @echo "  just open        open n8n in your browser"

# Install/update all Python deps
sync: _ensure-uv
    uv sync --all-extras

# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------

# Start everything (n8n + sidecar + Ollama)
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

# Start the sidecar locally for development (no Docker)
dev:
    uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Open the sidecar API docs
docs:
    @open http://localhost:8000/docs 2>/dev/null || xdg-open http://localhost:8000/docs

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

# Show logs (follow mode) — all services or specify one
logs *args:
    docker compose logs -f {{args}}

# Show logs for a specific service
log service:
    docker compose logs -f {{service}}

# Rebuild the sidecar container after code changes
rebuild:
    docker compose build sidecar
    docker compose up -d sidecar

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

# Pull the vision model for future photo analysis
pull-vision:
    docker exec automate-ollama ollama pull qwen2.5-vl:7b

# List downloaded models
models:
    docker exec automate-ollama ollama list

# Chat with the local model (interactive)
chat model=default_model:
    docker exec -it automate-ollama ollama run {{model}}

# ---------------------------------------------------------------------------
# Sidecar utilities
# ---------------------------------------------------------------------------

# Quick LLM health check via the sidecar
llm-test provider="ollama":
    @curl -s http://localhost:8000/llm/test?provider={{provider}} | python3 -m json.tool

# Detect Chrome bookmarks on this machine
bookmarks-detect:
    @curl -s http://localhost:8000/bookmarks/detect | python3 -m json.tool

# List recent bookmarks
bookmarks-list days="7" limit="20":
    @curl -s "http://localhost:8000/bookmarks/list?since_days={{days}}&limit={{limit}}" | python3 -m json.tool

# ---------------------------------------------------------------------------
# Linting & formatting
# ---------------------------------------------------------------------------

# Run all checks (lint + format check)
check: lint fmt-check

# Lint with ruff
lint:
    uv run ruff check .

# Lint and auto-fix
fix:
    uv run ruff check --fix .

# Format code with ruff
fmt:
    uv run ruff format .

# Check formatting without changing files
fmt-check:
    uv run ruff format --check .

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

# Run all tests
test *args:
    uv run pytest {{args}}

# Run tests with coverage
test-cov:
    uv run pytest --cov=services --cov=config --cov-report=term-missing

# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------

# Start Cloudflare Tunnel (edit config/cloudflare-tunnel.yml first)
tunnel:
    cloudflared tunnel --config config/cloudflare-tunnel.yml run automate

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

# Remove all generated/cached files
clean:
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    rm -rf htmlcov .coverage coverage.xml
    @echo "✓ Cleaned."

# Show project structure
tree:
    @find . -type f \
        -not -path './.git/*' \
        -not -path './.venv/*' \
        -not -path './__pycache__/*' \
        -not -path './.ruff_cache/*' \
        -not -name '*.pyc' \
        -not -name '.DS_Store' \
        -not -name 'uv.lock' \
        | sort

# Show status of all services
status:
    @echo "▸ Docker containers:"
    @docker compose ps 2>/dev/null || echo "  (not running)"
    @echo ""
    @echo "▸ n8n:      http://localhost:5678"
    @echo "▸ Sidecar:  http://localhost:8000/docs"
    @echo ""
    @echo "▸ Sidecar health:"
    @curl -s http://localhost:8000/health 2>/dev/null | python3 -m json.tool || echo "  (not reachable)"
    @echo ""
    @echo "▸ Ollama models:"
    @docker exec automate-ollama ollama list 2>/dev/null || echo "  (not running)"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

[private]
_ensure-uv:
    @command -v uv >/dev/null 2>&1 || { echo "Error: uv is required. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
