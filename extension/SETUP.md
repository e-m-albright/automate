# Automate Bookmark Sync — Setup Guide

## What it does

When you bookmark any page in Chrome, this extension immediately sends the URL, title, and folder to your Automate service for digestion (fetch content → summarize with LLM → categorize → tag).

After successful processing, the bookmark is moved to an **Automate/Processed** folder in your bookmarks so your bookmarks bar stays clean. (Configurable: you can also keep in place or delete.)

---

## Desktop Chrome (Laptop / Desktop)

### Install the extension

1. Open Chrome and navigate to `chrome://extensions`
2. Enable **Developer mode** (toggle in the top-right corner)
3. Click **Load unpacked**
4. Select the `extension/` folder from this repo (the folder containing `manifest.json`)
5. The extension appears in your toolbar with a blue "A" icon

### Configure

1. Right-click the extension icon → **Options** (or click the puzzle piece icon → Automate Bookmark Sync → three dots → Options)
2. Set the **Webhook URL**:
   - **Local dev:** `http://localhost:5678/webhook/bookmark` (n8n) or `http://localhost:8000/bookmarks/ingest` (sidecar direct)
   - **Deployed:** `https://your-server.example.com/webhook/bookmark`
3. Set **After processing** behavior:
   - **Move to folder** (default) — moves the bookmark to `Other Bookmarks/Automate/Processed`
   - **Keep in place** — leaves the bookmark where you put it
   - **Delete** — removes the bookmark after processing
4. Click **Save**

### Test it

1. Make sure your services are running (`just up` or `docker compose up`)
2. Bookmark any page (Cmd+D or Ctrl+D)
3. Check the n8n execution log at `http://localhost:5678` — you should see the webhook fire
4. Open `chrome://extensions` → Automate Bookmark Sync → **Service Worker** link → Console tab to see logs

### Updating the extension

When you `git pull` new changes to the `extension/` folder:
1. Go to `chrome://extensions`
2. Click the reload icon (circular arrow) on the Automate Bookmark Sync card
3. That's it — no uninstall/reinstall needed

---

## Mobile — iPhone / iPad (iOS)

Chrome on iOS doesn't support extensions. Instead, use an **iOS Shortcut** that appears in your Share Sheet. Same webhook, different trigger.

### Create the Shortcut

1. Open the **Shortcuts** app on your iPhone/iPad
2. Tap **+** to create a new shortcut
3. Tap **Add Action** and search for **"Receive input from Share Sheet"**
   - Set "If there's no input" to **"Ask For"** → **URLs**
4. Add action: **Get URLs from Input**
5. Add action: **Get Contents of URL**
   - Tap the action to configure it:
   - **URL:** `https://your-server.example.com/webhook/bookmark`
     (or `http://192.168.x.x:5678/webhook/bookmark` for local network)
   - **Method:** POST
   - **Headers:** add `Content-Type` = `application/json`
   - **Request Body:** JSON
     - Add field `url` → select the **URLs** variable from step 4
     - Add field `title` → type "Mobile bookmark" (or leave empty)
6. Name the shortcut: **"Bookmark to Automate"**
7. Tap the **info (i)** button at the bottom → enable **"Show in Share Sheet"**
8. Tap **Done**

### Use it

1. In Safari or Chrome on your phone, tap the **Share** button
2. Scroll down and tap **"Bookmark to Automate"**
3. The page URL is sent to your webhook instantly

### Tips

- Pin the shortcut: after using it once, it appears higher in your Share Sheet
- You can also add it to your Home Screen as a quick-launch icon
- For local-only testing, use your Mac's local IP (e.g. `http://192.168.1.100:5678/webhook/bookmark`) — your phone and laptop must be on the same Wi-Fi

---

## Mobile — Android

Chrome on Android also doesn't support extensions. Use one of these approaches:

### Option A: HTTP Shortcuts app (recommended)

1. Install [HTTP Shortcuts](https://play.google.com/store/apps/details?id=ch.rmy.android.http_shortcuts) (free, open source)
2. Create a new shortcut:
   - **Method:** POST
   - **URL:** `https://your-server.example.com/webhook/bookmark`
   - **Body:** JSON → `{ "url": "{url}", "title": "Android bookmark" }`
   - Use the app's **Share** integration so it appears in Android's share sheet
3. When browsing, tap Share → HTTP Shortcuts → your shortcut

### Option B: Firefox for Android

Firefox on Android supports extensions. You can port this extension to Firefox (Manifest V3 is cross-compatible with minor tweaks to `manifest.json`). This is more work but gives you the same automatic bookmark-on-create behavior.

---

## Security notes

- **No third-party servers.** The extension only talks to YOUR webhook URL. No analytics, no telemetry, no external calls.
- **Minimal permissions.** Only `bookmarks` (to listen for new bookmarks and move them) and `storage` (to save the webhook URL setting). No `tabs`, no `<all_urls>`, no `host_permissions`.
- **Only sends URL + title + folder.** No cookies, no page content, no auth tokens, no browsing history.
- **Self-hosted.** Loaded as an unpacked extension from your own repo. Not on the Chrome Web Store, so there's no supply chain risk from extension updates.
- **Encrypted in transit when deployed.** Point the webhook at your Cloudflare Tunnel URL (HTTPS).
- **Fails gracefully.** If the webhook is unreachable, the bookmark stays in Chrome untouched. The daily `/bookmarks/list` poll picks it up as a fallback.
