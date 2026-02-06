# Automate — TODO

I want to build these n8n capabilities in 2026

- an automated tagging system to help push emails with no action out of the inbox into the archive but tagged to be easily reviewed, and deleted if it doesn't pass a review or the llm is perhaps so incredibly confident we would want it deleted instead of wasting our time
- a generalized inbox tamer that helps you review in bulk emails that the system thinks you ought to see yourself because they don't fit a neat category that you're okay with not seeing yourself (promotions, receipts, shipping updates, ...)
- an email unsubscriber, after asking you if you want more emails of a form, have the llm navigate the unsubscribe flow for you if you say no. (i.e. an alaska airlines mileage promotion > ask if you want it, then unsubscribe for you)
- a newsletter distiller (catches anything that looks like a newsletter (list-unsubscribe header, bulk sender patterns, known newsletter domains, or senders I add to a list) - read, digest, visit URLs, and summarize the content. Use a config to know which senders to always include, and what my interests may be to rank the information parsed. Compile it into a daily briefing, delete the original newsletter, and send me the digest. Track which newsletters I never find useful and unsubscribe them

these should all work in batch on demand, but I'd also want some to be always on (email labeler, daily or weekly newsletter digester, ...)

When building n8n pipelines, prefer n8n nodes rather than workarounds (use the direct Ollama node, not a raw POST to the Ollama server) etc.

All emails should ideally be dealt with using a self-hosted model for privacy though we will need Gemini and others for quality improvements and or specialty tasks (e.g. Gemini for YouTube links in emails).

Please define some workflows for me both in step-by-step instructions for me to hand build then offer me json files I can import to jump start things.

---

## Architecture

**n8n** is the application. You build workflows in the visual editor at `http://localhost:5678`.

**Ollama** runs in Docker and is reachable from n8n at `http://ollama:11434`. Workflows use the built-in Ollama node or HTTP Request to the Ollama API for local LLM inference. Nothing leaves your machine unless you add cloud provider nodes (Claude, Gemini, etc.) yourself.

---

## Feature Backlog

### P0 — Core (build first)

- **Gmail OAuth setup in n8n** — Connect your Gmail (and your wife's) via n8n Credentials → Google OAuth2 (Gmail).
- **Email triage workflow (new emails)** — Gmail Trigger → Ollama/HTTP classify → Switch by category → Gmail actions (label/archive/star). Use Wait for Approval before destructive actions.
- **Inbox cleanup workflow (old emails)** — Manual Trigger → Gmail (batch of old inbox emails) → SplitInBatches → Ollama classify → review → Gmail actions.
- **Approval before destructive actions** — Use Wait/Form node or email digest for review; actions run only after approval.
- **Bookmark digestion workflow** — Schedule → your bookmark source (e.g. sheet, DB, or webhook from browser) → SplitInBatches → Ollama or HTTP to distill each URL → compile digest → email or save.

### P1 — Essential polish

- **Unsubscribe detection & execution** — LLM finds unsubscribe links; n8n HTTP Request hits them after approval.
- **Draft reply generation** — For actionable emails, Ollama drafts a reply → Gmail create draft.
- **Multi-account support** — Separate workflows or parameterized credential for your inbox vs your wife's.
- **Email labeling taxonomy** — Gmail labels like `automate/junk`, `automate/newsletter`, `automate/actionable`.
- **Digest delivery** — Daily summary of what was processed (Gmail send node at end of workflow).

### P2 — Content & knowledge

- **Astro blog integration** — Push digested content to your Astro journal (markdown or API).
- **RSS / site monitoring** — RSS Feed Read node → Ollama summarize → output.
- **YouTube summarization** — Detect YouTube URLs in content → route to Gemini (or similar) for video summary.
- **Bookmark organization** — Auto-tag/categorize; surface in digest (Chrome bookmark file is read-only from outside).

### P3 — Future

- **Google Photos / iCloud** — Watch new photos, vision model for OCR/analysis.
- **SMS / text ingestion** — Twilio or similar webhook → same classify → review → act pipeline.
- **Self-hosted LLM upgrades** — Larger Ollama models (e.g. qwen2.5:32b) as hardware allows.
- **Always-on deployment** — VPS + Cloudflare Tunnel for n8n.

---

## Design Principles

1. **No destructive action without approval.** Everything goes through a review step.
2. **Privacy first.** Use local Ollama by default; add cloud only where needed.
3. **n8n is the UI.** No custom dashboard; execution history in n8n.
4. **Incremental cleanup.** Process in manageable batches (e.g. 50 emails at a time).
5. **Prefer n8n native nodes** (Ollama node, Gmail, etc.) over custom HTTP where possible.
