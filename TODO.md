# Automate — TODO

## Architecture Overview

**n8n is the application.** You build workflows in the visual editor at `localhost:5678`.

**The Python sidecar** (`localhost:8000`) exists for two things n8n can't do natively:

1. **Privacy-first LLM routing** — screens content locally via Ollama before optionally sending clean content to cloud LLMs (Claude/Gemini). n8n has no concept of "run this on local model first, check the result, then conditionally route to a different model." The sidecar's `POST /llm/analyze` handles this in one call.

2. **Chrome bookmark parsing** — n8n runs in Docker and can't read your local filesystem. The sidecar reads Chrome's `~/Library/Application Support/Google/Chrome/Default/Bookmarks` JSON file, parses the nested folder structure, converts Chrome's Windows-epoch timestamps, and returns clean JSON that n8n can iterate over.

**Everything else is n8n.** Gmail, scheduling, approval, labeling, archiving, deleting — all built-in n8n nodes.

### How the sidecar gets used inside n8n

The sidecar is not a custom n8n node. It's a plain HTTP API running alongside n8n in Docker. n8n workflows call it via **HTTP Request** nodes:

- `POST http://sidecar:8000/llm/analyze` — send email body or article text, get back classification + privacy flag
- `POST http://sidecar:8000/llm/complete` — direct LLM call (bypass privacy screening)
- `GET http://sidecar:8000/bookmarks/list?since_days=7` — get recent bookmarks as JSON
- `POST http://sidecar:8000/bookmarks/digest` — send a URL, get back summary/takeaways/tags

Inside Docker, n8n reaches the sidecar at `http://sidecar:8000` (container name). From your machine it's `http://localhost:8000`.

### What the sidecar code does (file by file)

| File | What | Why n8n can't do it |
|------|------|---------------------|
| `main.py` | FastAPI with 6 endpoints | Entry point — glues everything together |
| `services/llm/router.py` | Two-pass privacy routing: screen locally → route to cloud | n8n has no "run local LLM, check result, conditionally route to different LLM" primitive |
| `services/llm/providers/ollama.py` | Talks to Ollama API | Privacy screening pass — always local, nothing leaves your machine |
| `services/llm/providers/claude.py` | Talks to Anthropic API | Optional high-quality analysis for clean content |
| `services/llm/providers/gemini.py` | Talks to Google Gemini API | Optional — can process YouTube videos |
| `services/llm/base.py` | Abstract provider interface | Keeps all providers swappable |
| `services/bookmarks/ingester.py` | Reads Chrome Bookmarks JSON, fetches URLs, extracts content, distills with LLM | n8n is sandboxed in Docker — can't read local files or do HTML→markdown extraction |
| `config/settings.py` | Pydantic settings from .env | Standard config management |

---

## Feature Backlog

### P0 — Core (build first)

- [ ] **Gmail OAuth setup in n8n**
  Connect your Gmail account (and your wife's) via n8n's built-in credential manager.
  `Settings → Credentials → Add Credential → Google OAuth2 (Gmail)`
  No code needed — n8n handles the OAuth flow.

- [ ] **Email triage workflow (new emails)**
  Triggers on new email → sidecar classifies → routes by category → takes action.
  *n8n workflow:* Gmail Trigger → HTTP Request to `/llm/analyze` → Code node (parse JSON) → Switch (route by category) → Gmail actions (label/archive/star).
  Starter template: `n8n/workflows/01-email-triage.json`

- [ ] **Inbox cleanup workflow (old emails)**
  Manual trigger → fetch batch of 50 old emails → classify each → review → act.
  *n8n workflow:* Manual Trigger → Gmail (getAll, query `is:inbox older_than:30d`) → SplitInBatches → HTTP Request to `/llm/analyze` → Code (format review) → human review step → Gmail actions.
  Starter template: `n8n/workflows/02-inbox-cleanup.json`
  *For your wife:* Same workflow, different Gmail credential. Run it repeatedly, 50 at a time, until inbox is under control.

- [ ] **Approval before destructive actions**
  Nothing gets deleted/archived/unsubscribed without your say-so.
  *n8n approach:* Use the **Wait** node or **Form** node to pause execution and present a review. Or batch up classifications and email yourself a summary to approve.
  *Simplest v1:* Workflow classifies, then emails you a digest with "here's what I'd do." You reply or click a webhook link to approve. Actions execute only after approval.

- [ ] **Bookmark digestion workflow**
  Daily schedule → fetch new bookmarks from sidecar → distill each → output digest.
  *n8n workflow:* Schedule Trigger → HTTP Request to `/bookmarks/list` → Code (split array) → SplitInBatches → HTTP Request to `/bookmarks/digest` → Code (format markdown) → output (email/file/webhook).
  Starter template: `n8n/workflows/03-bookmark-digest.json`

### P1 — Essential polish

- [ ] **Unsubscribe detection & execution**
  When classifying newsletters/junk, have the LLM look for unsubscribe links in the email HTML.
  *Approach:* Extend the `/llm/analyze` prompt to ask for unsubscribe URLs. Add an n8n Code node that hits the unsubscribe link via HTTP Request if approved.

- [ ] **Draft reply generation**
  For emails classified as ACTIONABLE, generate a draft reply.
  *n8n workflow:* After classification, if actionable → HTTP Request to `/llm/complete` with "Draft a reply to this email: ..." → Gmail node (create draft, not send).

- [ ] **Multi-account support**
  Your inbox + your wife's inbox as separate n8n workflows with different Gmail credentials.
  *Approach:* Duplicate the workflows, swap the credential. Or parameterize with n8n variables.

- [ ] **Email labeling taxonomy**
  Create Gmail labels like `automate/junk`, `automate/newsletter`, `automate/actionable` and have the triage workflow apply them.
  *n8n approach:* Gmail node → addLabels operation. Create labels manually in Gmail first, or use Gmail API via HTTP Request to create them programmatically.

- [ ] **Digest delivery**
  Email yourself a daily summary of what was processed.
  *n8n approach:* At the end of any workflow, add a Gmail (send) node that emails you the results.

### P2 — Content & knowledge management

- [ ] **Astro blog integration**
  Push digested bookmarks and email summaries to your Astro journal as markdown posts.
  *Approach:* n8n writes markdown files to a git repo (via Code node + exec, or GitHub API node), which triggers an Astro rebuild. Or POST to an API endpoint on your Astro site.

- [ ] **RSS / site monitoring**
  Watch specific publications for new content.
  *n8n approach:* n8n has a built-in **RSS Feed Read** node. Schedule Trigger → RSS Read → SplitInBatches → HTTP Request to `/llm/analyze` or `/bookmarks/digest` → output.

- [ ] **YouTube video summarization**
  For bookmarked YouTube links, use Gemini to summarize the video.
  *Approach:* In the bookmark digest workflow, detect YouTube URLs → route to `/llm/complete` with `provider: "gemini"` and a prompt asking to summarize the video at that URL. Gemini can process YouTube natively.

- [ ] **Bookmark organization / tagging**
  Auto-tag and categorize bookmarks, potentially move them into Chrome folders.
  *Current:* The `/bookmarks/digest` endpoint already returns `suggested_tags` and `category`. Surfacing this is easy. Actually moving bookmarks in Chrome is harder — Chrome's Bookmarks file is read-only from outside Chrome.

### P3 — Future expansions

- [ ] **Google Photos / iCloud watcher**
  Watch for new photos, analyze them with a vision model.
  *Example:* Thumbs-up at a bookshelf → OCR book titles → look up reviews → suggest which to buy.
  *Approach:* Google Photos API → download image → POST to sidecar with vision model (Qwen2.5-VL-7B via Ollama, or Gemini for cloud). Sidecar would need a new `/vision/analyze` endpoint.
  *Status:* Architecturally accounted for (the LLM router supports vision models in config), but no code yet. Build when ready.

- [ ] **SMS / text message ingestion**
  Process incoming texts through the same classify → review → act pipeline.
  *Approach:* Twilio webhook → n8n webhook trigger → same sidecar `/llm/analyze` flow. Or Apple Messages via shortcuts/automation.

- [ ] **Sensitive content dashboard**
  See what got flagged as sensitive vs. clean, which provider handled what.
  *Approach:* The sidecar already returns `kept_local` and `provider_used` on every `/llm/analyze` call. n8n can log these to Google Sheets, Airtable, or a simple JSON file.

- [ ] **Self-hosted LLM upgrades**
  Move from Qwen 2.5 7B to a larger model as hardware allows.
  *Options:* Qwen 2.5 32B (needs RTX 4090 / 32GB Mac), Qwen 2.5 72B (needs 2x RTX 4090), GPT-OSS-120B (needs H100).
  *How:* Just change `OLLAMA_MODEL` in `.env` and `just pull-model qwen2.5:32b`. No code changes.

- [ ] **Always-on deployment**
  Move from local Docker to a VPS behind Cloudflare Tunnel.
  *Approach:* $5/mo VPS (Hetzner/Fly.io) running the same `docker-compose.yml`. Cloudflare Tunnel for secure access without opening ports. See `config/deploy.md` and `config/cloudflare-tunnel.yml`.

---

## Design Principles

1. **No destructive action without approval.** Everything goes through a review step.
2. **Privacy first.** Local LLM screens everything. Cloud only sees clean content, and only if you opt in.
3. **n8n is the UI.** No custom dashboard to build or maintain. You see everything in n8n's execution history.
4. **Incremental cleanup.** Process 50 emails at a time, not 10,000. Manageable batches you can review.
5. **Multi-model.** Ollama for privacy, Claude for quality, Gemini for YouTube/multimodal. Mix per task.
6. **Extensible sources.** Email, bookmarks, RSS, photos, texts — same pipeline, different trigger.
