# Automate

Privacy-first email and content automation, powered by [n8n](https://n8n.io/) and local LLMs.

## What is this?

**n8n is the application.** You build, edit, and monitor all your automations in the n8n visual editor at `http://localhost:5678`. A small Python sidecar handles two things n8n can't do natively: parsing your Chrome bookmarks file and routing LLM calls through a local privacy screen.

```
┌─────────────────────────────────────────────────────┐
│  n8n  (http://localhost:5678)                       │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐    │
│  │ Gmail    │  │ Schedule │  │ Wait for       │    │
│  │ Trigger  │  │ Trigger  │  │ Approval node  │    │
│  └────┬─────┘  └────┬─────┘  └────────────────┘    │
│       │              │                               │
│       ▼              ▼                               │
│  ┌──────────────────────────┐                       │
│  │ HTTP Request to sidecar  │◄── privacy screening  │
│  │ POST /llm/analyze        │    + LLM routing       │
│  └──────────────────────────┘                       │
│       │                                              │
│       ▼                                              │
│  ┌──────────────────────────┐                       │
│  │ Gmail: Label / Archive / │◄── only after you     │
│  │ Delete / Draft Reply     │    approve in n8n UI   │
│  └──────────────────────────┘                       │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│  Sidecar :8000  │────►│  Ollama :11434   │
│  (Python/Fast   │     │  (local LLM,     │
│   API)          │────►│   nothing leaves  │
│                 │     │   your machine)   │
│  • /llm/analyze │     └──────────────────┘
│  • /bookmarks/* │              │
└─────────────────┘              │ (if content is clean)
                                 ▼
                        ┌──────────────────┐
                        │  Claude / Gemini │
                        │  (optional,      │
                        │   cloud)         │
                        └──────────────────┘
```

## Quick start

```bash
# Prerequisites: docker, uv, just
# Install uv:  curl -LsSf https://astral.sh/uv/install.sh | sh
# Install just: brew install just

just setup         # install Python deps, create .env
just up            # start n8n + sidecar + Ollama
just pull-model    # download Qwen 2.5 7B (~4GB)
just open          # open n8n in your browser
```

Then build your workflows in the n8n UI.

## Services

| Service | URL | What it does |
|---------|-----|-------------|
| **n8n** | http://localhost:5678 | Your main UI — build workflows, connect Gmail, approve actions |
| **Sidecar** | http://localhost:8000 | Bookmark parsing + LLM privacy routing (called by n8n) |
| **Sidecar docs** | http://localhost:8000/docs | API reference for the sidecar endpoints |
| **Ollama** | http://localhost:11434 | Local LLM inference |

## Building workflows in n8n

n8n is a visual workflow builder. You drag nodes, connect them, and they run on a schedule or trigger. Here's how to build each automation:

### Email triage

1. **Gmail Trigger** node → fires on new emails (or use Schedule Trigger to batch process)
2. **HTTP Request** node → `POST http://sidecar:8000/llm/analyze` with the email body
   - The sidecar screens for sensitive content locally, then classifies
3. **Switch** node → route by category (junk, newsletter, actionable, etc.)
4. **Wait for Approval** node → you review proposed actions in the n8n UI
5. **Gmail** node → label, archive, delete, or draft a reply

### Bookmark digestion

1. **Schedule Trigger** → runs daily
2. **HTTP Request** → `GET http://sidecar:8000/bookmarks/list?since_days=1`
3. **SplitInBatches** → process each bookmark
4. **HTTP Request** → `POST http://sidecar:8000/bookmarks/digest` with each URL
5. Do what you want with the summary (email it, save to file, push to your blog)

### Inbox cleanup (for your wife's 1000s of old emails)

1. **Manual Trigger** (or Schedule) → kicks off a batch
2. **Gmail** node → search `is:inbox older_than:30d`, limit to 50
3. **SplitInBatches** → process each email
4. **HTTP Request** → `POST http://sidecar:8000/llm/analyze` for each
5. **Wait for Approval** → batch review in the n8n UI
6. **Gmail** → archive junk, unsubscribe from newsletters, label the rest

### Key n8n concepts

- **Gmail node**: Connect your Google account in n8n's credentials UI (Settings → Credentials). Handles OAuth for you.
- **Wait for Approval**: Pauses the workflow and shows you a review in the n8n UI. Nothing happens until you click approve.
- **HTTP Request node**: Calls the sidecar. Use `http://sidecar:8000` (Docker container name).
- **Error Trigger**: Add one to catch failures and notify you.

## Privacy model

Every piece of content goes through a two-pass system:

1. **Pass 1 (always local):** Ollama screens for sensitive content (PII, financial, medical). Nothing leaves your machine.
2. **Pass 2 (configurable):** Clean content can route to Claude/Gemini for better analysis. Sensitive content stays local.

```bash
# .env — control the routing
DEFAULT_PROVIDER=ollama                    # everything local by default
HIGH_QUALITY_PROVIDER=claude               # route clean content here
CLAUDE_API_KEY=sk-ant-...                  # optional
```

## Sidecar API

The sidecar only does two things:

### LLM routing

```bash
# Privacy-first analysis (screens locally, then routes)
curl -X POST http://localhost:8000/llm/analyze \
  -H "Content-Type: application/json" \
  -d '{"content": "...", "analysis_prompt": "Classify this email..."}'

# Direct completion (bypass screening)
curl -X POST http://localhost:8000/llm/complete \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Summarize this article...", "provider": "ollama"}'
```

### Bookmark parsing

```bash
# Detect Chrome bookmarks
curl http://localhost:8000/bookmarks/detect

# List recent bookmarks
curl "http://localhost:8000/bookmarks/list?since_days=7&limit=20"

# Digest a single URL
curl -X POST http://localhost:8000/bookmarks/digest \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article", "title": "Some Article"}'
```

## Common commands

```bash
just --list        # see everything

just up            # start all services
just open          # open n8n in browser
just logs          # follow all logs
just log n8n       # follow n8n logs only
just status        # check everything

just pull-model    # download default LLM
just chat          # chat with local model
just llm-test      # test LLM health

just check         # lint + format check
just fix           # auto-fix lint issues
just test          # run tests
just clean         # remove caches
```

## Project structure

```
automate/
├── docker-compose.yml          # n8n + sidecar + Ollama
├── main.py                     # Sidecar API (bookmarks + LLM routing)
├── Dockerfile                  # Sidecar container
├── config/
│   ├── settings.py             # Sidecar config (LLM providers, etc.)
│   ├── cloudflare-tunnel.yml   # Deployment config
│   └── deploy.md               # Deployment guide
├── services/
│   ├── llm/                    # Multi-provider LLM router
│   │   ├── router.py           #   Privacy-first screen → analyze
│   │   └── providers/          #   Ollama, Claude, Gemini
│   └── bookmarks/
│       └── ingester.py         #   Chrome bookmark parser + URL distiller
├── pyproject.toml              # Deps, ruff, pytest config
└── justfile                    # Task runner
```

## Deployment

**Local** (current): Docker Compose on your machine.

**Always-on**: Small VPS ($5/mo) with Cloudflare Tunnel for n8n access from anywhere. See `config/deploy.md`.

## Future plans

- **Photo analysis**: Watch Google Photos / iCloud → detect scenes → extract info
- **RSS monitoring**: Watch sites and publications for new content
- **Astro blog integration**: Push digested content to your journal
- **Text/SMS ingestion**: Process incoming messages through the same pipeline
