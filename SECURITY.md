# Security checklist for public repo

Before pushing to a public GitHub repo, verify the following.

## ✅ Already in good shape

- **`.env`** — In `.gitignore`; not committed. Do not remove it from ignore or commit it. (It contains n8n password, API key, and optional cloud API keys.)
- **`n8n_data/`** — Ignored. n8n stores credentials and workflow DB here; must never be committed.
- **`n8n/credentials/`** — Ignored. Extra n8n credential storage.
- **Export script** — Strips `credentials` from each node when exporting, so workflow JSON in the repo does not contain n8n credential references.

## ⚠️ Workflow JSON (n8n/workflows/)

Committed workflow files do **not** contain API keys or credential secrets. They do contain:

| Item | Risk | Note |
|------|------|------|
| **webhookId** | Low | UUIDs used by n8n for webhook paths. If someone has your n8n URL they could try to trigger webhooks; on import, other instances get new IDs. Only a concern if your n8n is publicly reachable. |
| **Gmail label IDs** (e.g. `Label_3690428769571063072`) | Low | Specific to a Gmail account. Reveal that you use certain labels; not a credential. Others would need to replace with their own when importing. |
| **Workflow / node IDs** | Negligible | Internal n8n IDs; replaced on import. |

If you want to redact before publishing: remove or genericize `webhookId` and Gmail `labelIds` / filter `q` values in the JSON (e.g. with a script or manual edit). Optional, not required for “no secrets” safety.

## Before first push

1. Run `git status` and `git diff` — ensure `.env` and any `n8n_data` or credential files are not staged.
2. Confirm: `git check-ignore -v .env` prints `.gitignore:65:.env .env`.
3. If `.env` was ever committed in the past, purge it from history (e.g. `git filter-repo` or BFG) and rotate the n8n API key and password.

## After publishing

- Rotate **N8N_API_KEY** and **N8N_PASSWORD** if you had ever committed `.env` or pushed to a non-private repo by mistake.
- Keep n8n behind auth; do not expose the n8n UI/API to the internet without authentication and HTTPS.
