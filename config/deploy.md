# Deployment Guide

## Local Development (current setup)

```bash
# First time
cp .env.example .env
# Edit .env with your API keys
bash scripts/setup.sh
```

## Always-On Deployment

n8n needs a persistent runtime (long-running process, cron scheduling),
so pure Cloudflare Workers won't work. Two options:

### Option A: VPS + Cloudflare Tunnel (recommended)
- $5/mo VPS (Hetzner, Fly.io, Railway)
- Run Docker Compose on the VPS
- Cloudflare Tunnel for secure access (no open ports)
- See `config/cloudflare-tunnel.yml`

### Option B: Home server + Cloudflare Tunnel
- Run Docker Compose on a home machine (Mac Mini, NUC, etc.)
- Cloudflare Tunnel for access from anywhere
- Same config, just runs from home

### GPU for local LLM
- If self-hosting Ollama on the VPS, you need a GPU VPS (~$20-40/mo)
- Alternative: run Ollama at home, API services on VPS
- Or: use cloud LLM providers and skip the GPU entirely
