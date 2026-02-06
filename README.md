# Automate

Privacy-first email and content automation, powered by [n8n](https://n8n.io/) and local LLMs via [Ollama](https://ollama.com/).

## What is this?

**n8n is the application.** You build, edit, and monitor all your automations in the n8n visual editor at `http://localhost:5678`. Workflows use **Ollama** for local LLM inference — nothing leaves your machine unless you add cloud nodes (e.g. Claude, Gemini) yourself.

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
│  │ Ollama / HTTP Request   │   Local LLM or       │
│  │ (classify, summarize)   │   direct Ollama API   │
│  └──────────────────────────┘                       │
│       │                                              │
│       ▼                                              │
│  ┌──────────────────────────┐                       │
│  │ Gmail: Label / Archive / │                       │
│  │ Delete / Draft Reply     │                       │
│  └──────────────────────────┘                       │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────┐
│  Ollama :11434   │  Local LLM (qwen2.5, llama3.2, etc.)
└──────────────────┘
```

## Quick start

```bash
# Prerequisites: docker, just
# Install just: brew install just

just setup         # create .env, start services
just up            # start n8n + Ollama
just pull-model    # download default LLM (qwen2.5:7b)
just open          # open n8n in your browser
```

Then build your workflows in the n8n UI.

## Services

| Service | URL | What it does |
|---------|-----|-------------|
| **n8n** | http://localhost:5678 | Your main UI — build workflows, connect Gmail, approve actions |
| **Ollama** | http://localhost:11434 | Local LLM inference |

## Building workflows in n8n

n8n is a visual workflow builder. Use **Ollama** nodes or **HTTP Request** to `http://ollama:11434` (from inside Docker) or `http://localhost:11434` (from your machine) for chat/completions.

### Key n8n concepts

- **Gmail node**: Connect your Google account in n8n's credentials UI (Settings → Credentials). Handles OAuth for you.
- **Wait for Approval**: Pauses the workflow and shows you a review in the n8n UI.
- **Ollama node**: Use the built-in Ollama node with base URL `http://ollama:11434` when n8n runs in Docker.
- **HTTP Request**: For custom prompts, POST to `http://ollama:11434/api/chat` with `model`, `messages`, `stream: false`.

## Common commands

```bash
just --list        # see everything

just up            # start all services
just open         # open n8n in browser
just logs         # follow all logs
just log n8n      # follow n8n logs only
just status       # check everything

just pull-model   # download default LLM
just chat         # chat with local model
just models       # list Ollama models
```

## Project structure

```
automate/
├── docker-compose.yml   # n8n + Ollama
├── justfile             # Task runner
├── n8n/
│   └── workflows/       # Exported n8n workflow JSONs
├── scripts/
│   ├── setup.sh         # First-time setup
│   └── export-workflows.sh
└── .env.example         # Copy to .env and edit
```

## Deployment

**Local**: Docker Compose on your machine (current).

**Always-on**: Run the same stack on a VPS and expose n8n via Cloudflare Tunnel or similar.
