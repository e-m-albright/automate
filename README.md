# Automate

Email and content automation with [n8n](https://n8n.io/) and [Ollama](https://ollama.com/) for local LLM.

## Quick start

```bash
just setup    # create .env, turn on services
just up       # after the initial setup, turn on services this way
just open     # open n8n at http://localhost:5678
just import-workflows
```

**Services:** n8n at `http://localhost:5678`, Ollama at `http://localhost:11434`. Use the Ollama node in n8n with base URL `http://ollama:11434` when running in Docker.

You'll need to configure your gmail / gemini / ollama as you desire to enable the automations.

[Check this for gemini pricing.](https://ai.google.dev/gemini-api/docs/pricing)

Finally, publish the workflows and all should be running.

## Commands


| Command                        | Description                                         |
| ------------------------------ | --------------------------------------------------- |
| `just up` / `down` / `restart` | Start, stop, or restart containers                  |
| `just open`                    | Open n8n in the browser                             |
| `just logs` / `just log n8n`   | Follow logs                                         |
| `just status`                  | Show containers and Ollama models                   |
| `just pull-model`              | Pull default Ollama model (qwen2.5:7b)              |
| `just export-workflows`        | Export n8n workflows to `n8n/workflows/`            |
| `just import-workflows`        | Import workflow JSON from `n8n/workflows/` into n8n |


Set `N8N_API_KEY` in `.env` (create at n8n → Settings → API) for export/import.

## Project structure

```
automate/
├── docker-compose.yml   # n8n + Ollama
├── justfile
├── n8n/workflows/       # Version-controlled workflow JSON
├── scripts/
│   ├── setup.sh
│   ├── export-workflows.sh
│   └── import-workflows.sh
└── .env.example
```

## Deployment

Run locally with Docker Compose. For always-on access, run the same stack on a VPS and expose n8n (e.g. Cloudflare Tunnel).