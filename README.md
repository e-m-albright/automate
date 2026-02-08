# Automate

Email and content automation with [n8n](https://n8n.io/), [Ollama](https://ollama.com/) for local LLM work, and workflows leaning on Gemini for commercial LLM work.

## Current Workflows

1. Email label organizer. All new emails + batches of old emails are sent to an LLM to apply one of your current list of Gmail labels, and archive labels you select to help keep your inbox clear
1. An agent set up to chat with you over your emails to potentially operate autonomously on modifying email labels - far less tested + likely a less stable experience
1. A content brief (WIP, not yet implemented) - consume news / newsletter content to consolidate + provide page summaries to reduce catch-up fatigue


## Follow Up Work
- Host on https://console.hetzner.com/projects w/ Cloudflare Tunnel if always on is desired
- Set up label quality evals
- Add guardrails to check for malicious email content being passed to LLM
- Tweak thread/message interactions - presently email threads will get 1 labeling pass per message, may not be ideal experience
- Improve label quality by using the whole email not the simplified "snippet"
- Add a label creator for one time or dynamic label management

## Quick start

```bash
just setup    # create .env, turn on services
just up       # after the initial setup, turn on services this way
just open     # open n8n at http://localhost:5678
just import-workflows
```

**Services:** n8n at `http://localhost:5678`, Ollama at `http://localhost:11434`. Use the Ollama node in n8n with base URL `http://ollama:11434` when running in Docker.

You'll need to configure your gmail / gemini / ollama as you desire to enable the automations.

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

## Ollama / Gemini Use

- **[Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)**
- **[Billed usage](https://aistudio.google.com/usage?timeRange=last-28-days)**

## My Email Labels
```
# "Processed" email breadcrumb, hidden
.n8n

# Auto-archive
Content/
├── Educational Reference
├── Newsletter
└── Product Update

Financial/
├── Banking
├── Insurance
├── Investments
├── Subscriptions
├── Taxes
└── Utilities & Bills

Personal/
├── Auto
├── Civic
├── Health
├── House
├── Kid
├── Travel
└── Wedding

Priority/
├── Calendar Events
├── Legal
└── Security & Login

Professional/
├── Networking
├── Opportunities
└── Recruiters

# Auto-archive
Shopping/
├── Customer Service
├── Fulfillment
├── Housing Search
├── Promotion
└── Receipt
 ```