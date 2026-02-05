# Automate

Privacy-first email and content automation powered by local LLMs.

Automate triages your inbox, distills your bookmarks, and organizes your content — without blasting your personal data to cloud APIs unless you explicitly opt in.

## How it works

```
Content Sources          Local LLM (Pass 1)         Cloud LLM (Pass 2, optional)
─────────────────       ──────────────────────      ────────────────────────────
Gmail (you)        ──►  Screen for sensitivity  ──► Deep analysis (Claude/Gemini)
Gmail (wife)       ──►  Classify & categorize   ──► Summarize & draft replies
Chrome bookmarks   ──►  Extract & distill       ──► Tag & organize
RSS feeds          ──►                              │
Photos (future)    ──►                              ▼
                                                 Review Queue
                                                    │
                                          You approve/reject
                                                    │
                                                    ▼
                                              Execute actions
                                        (label, archive, delete,
                                         unsubscribe, draft reply,
                                         publish to Astro blog)
```

**Nothing destructive happens without your approval.** Every proposed action goes through a review queue where you approve or reject in manageable batches.

## Quick start

```bash
# Prerequisites: docker, uv, just
# Install uv:  curl -LsSf https://astral.sh/uv/install.sh | sh
# Install just: brew install just

# Clone and setup
just setup

# Or step by step:
cp .env.example .env          # add your API keys
just sync                      # install Python deps
just up                        # start n8n + API + Ollama
just pull-model                # download Qwen 2.5 7B (~4GB)
```

## Services

| Service | URL | Purpose |
|---------|-----|---------|
| API | http://localhost:8000 | FastAPI backend — all processing logic |
| API docs | http://localhost:8000/docs | Interactive Swagger UI |
| n8n | http://localhost:5678 | Workflow automation & scheduling |
| Ollama | http://localhost:11434 | Local LLM inference |

## Common commands

```bash
just --list        # see all available commands

# Development
just dev           # run API locally (hot reload, no Docker)
just check         # lint + format check
just fix           # auto-fix lint issues
just fmt           # format code
just test          # run tests

# Docker
just up            # start all services
just down          # stop all services
just logs          # follow all logs
just log api       # follow API logs only
just rebuild       # rebuild API container after code changes

# Local LLM
just pull-model    # pull default model (qwen2.5:7b)
just pull-vision   # pull vision model for future photo analysis
just models        # list downloaded models
just chat          # interactive chat with local model

# Status
just status        # health check everything
just llm-test      # test LLM provider
```

## Architecture

### Privacy-first LLM routing

Every piece of content runs through a two-pass system:

1. **Pass 1 (always local):** Ollama with Qwen 2.5 screens for sensitive content (PII, financial, medical, personal). Nothing leaves your machine.
2. **Pass 2 (configurable):** Clean content can optionally route to Claude, Gemini, or OpenAI for higher-quality analysis. Sensitive content stays local.

You control routing per-task in `.env`:

```bash
# Default: everything stays local
DEFAULT_PROVIDER=ollama

# Or route clean content to Claude for better quality
HIGH_QUALITY_PROVIDER=claude
CLAUDE_API_KEY=sk-ant-...
```

### Supported LLM providers

| Provider | Best for | Privacy |
|----------|----------|---------|
| **Ollama** (local) | Screening, classification, basic summarization | Full — nothing leaves your machine |
| **Claude** | Deep analysis, reply drafting, nuanced categorization | Cloud — only non-sensitive content |
| **Gemini** | YouTube video summarization, multimodal | Cloud — only non-sensitive content |

### Recommended local models

| Model | Parameters | VRAM | Use case |
|-------|-----------|------|----------|
| Qwen 2.5 7B | 7B | ~6GB | Default — email triage, classification |
| Qwen 2.5 32B | 32B | ~20GB | Higher quality, if you have an RTX 4090 or 32GB Mac |
| Qwen 2.5 VL 7B | 7B | ~8GB | Future — photo/image analysis |

## Project structure

```
automate/
├── main.py                     # FastAPI app — all API endpoints
├── config/
│   └── settings.py             # Pydantic settings, LLM/Gmail config
├── services/
│   ├── llm/                    # Multi-provider LLM router
│   │   ├── router.py           #   Privacy-first screen-then-analyze
│   │   └── providers/          #   Ollama, Claude, Gemini
│   ├── gmail/                  # Gmail integration
│   │   ├── client.py           #   API client (read + write operations)
│   │   └── classifier.py       #   AI email classification
│   ├── review/                 # Approval workflow
│   │   └── queue.py            #   Batch proposals, approve/reject
│   ├── actions/                # Post-approval execution
│   │   └── executor.py         #   Label, archive, delete, unsubscribe, draft
│   ├── bookmarks/              # Chrome bookmark digestion
│   │   └── ingester.py         #   Parse, fetch, summarize
│   ├── content/                # Content publishing
│   │   └── astro_publisher.py  #   Push digests to Astro blog
│   ├── photos_stub/            # Future: Google Photos / iCloud
│   │   └── watcher.py          #   Architecture documented, not yet built
│   └── database.py             # SQLAlchemy models
├── n8n/workflows/              # n8n workflow templates
├── docker-compose.yml          # n8n + API + Ollama
├── pyproject.toml              # Dependencies, ruff, pytest config
└── justfile                    # Task runner recipes
```

## Email pipeline

```
1. Fetch batch (50 emails)
2. Screen each for sensitivity (local LLM)
3. Classify: junk, newsletter, receipt, social, actionable, FYI, personal, important
4. Propose actions: archive, delete, unsubscribe, label, draft reply
5. Create review batch (you see a summary)
6. You approve/reject per-item or in bulk
7. Execute approved actions in Gmail
```

## Bookmark pipeline

```
1. Read Chrome's local Bookmarks file (no extension needed)
2. Fetch each URL, extract article content
3. Distill with LLM: summary, key takeaways, category, tags
4. Publish as markdown to your Astro blog
```

## Configuration

Copy `.env.example` to `.env` and fill in what you need:

```bash
# Required for Gmail
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Optional — cloud LLM providers (local Ollama works without these)
CLAUDE_API_KEY=...
GEMINI_API_KEY=...

# Processing
EMAIL_BATCH_SIZE=50            # emails per review batch
```

## Deployment

**Local** (current): Docker Compose on your machine.

**Always-on**: Small VPS ($5/mo) with Cloudflare Tunnel. See `config/deploy.md`.

```bash
just tunnel    # start Cloudflare Tunnel
```

## Future plans

- **Photo analysis**: Point at Google Photos or iCloud, detect scenes (e.g., thumbs-up at a bookshelf → scan for book titles → look up reviews)
- **RSS/site monitoring**: Watch publications, alert on new content matching your interests
- **Reflex dashboard**: Full review UI beyond the API
- **Text/SMS ingestion**: Process incoming messages through the same pipeline
