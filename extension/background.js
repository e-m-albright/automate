/**
 * Automate Bookmark Sync — background service worker
 *
 * Listens for Chrome bookmark creation events and POSTs to your
 * Automate sidecar or n8n webhook for ingestion + digestion.
 *
 * After successful processing, the bookmark is moved to a
 * "Automate/Processed" folder (configurable) so your bookmarks
 * bar stays clean.
 *
 * Configuration (set via Options page):
 *   webhookUrl  — where to POST (default: n8n webhook)
 *   afterAction — what to do after processing: "move", "delete", or "keep"
 *   processedFolder — folder name to move processed bookmarks into
 */

// Default points to n8n webhook — content pipeline (workflow 05) handles
// classification, routing, blog publishing, and cleanup.
const DEFAULT_WEBHOOK_URL = "http://localhost:5678/webhook/content";
const DEFAULT_AFTER_ACTION = "move"; // "move" | "delete" | "keep"
const DEFAULT_PROCESSED_FOLDER = "Automate/Processed";

/**
 * Get settings from chrome.storage.
 */
async function getSettings() {
  const result = await chrome.storage.sync.get([
    "webhookUrl",
    "afterAction",
    "processedFolder",
  ]);
  return {
    webhookUrl: result.webhookUrl || DEFAULT_WEBHOOK_URL,
    afterAction: result.afterAction || DEFAULT_AFTER_ACTION,
    processedFolder: result.processedFolder || DEFAULT_PROCESSED_FOLDER,
  };
}

/**
 * Get the folder path for a bookmark by walking up the tree.
 */
async function getFolderPath(parentId) {
  const parts = [];
  let currentId = parentId;

  while (currentId && currentId !== "0") {
    try {
      const nodes = await chrome.bookmarks.get(currentId);
      if (nodes.length > 0 && nodes[0].title) {
        parts.unshift(nodes[0].title);
      }
      currentId = nodes[0].parentId;
    } catch {
      break;
    }
  }

  return parts.join("/");
}

/**
 * Find or create a bookmark folder by path (e.g. "Automate/Processed").
 * Creates intermediate folders as needed under "Other Bookmarks".
 */
async function getOrCreateFolder(folderPath) {
  const parts = folderPath.split("/").filter(Boolean);

  // Start from "Other Bookmarks" (id "2" in Chrome)
  let parentId = "2";

  for (const name of parts) {
    const children = await chrome.bookmarks.getChildren(parentId);
    const existing = children.find(
      (c) => c.title === name && !c.url
    );

    if (existing) {
      parentId = existing.id;
    } else {
      const created = await chrome.bookmarks.create({
        parentId: parentId,
        title: name,
      });
      parentId = created.id;
    }
  }

  return parentId;
}

/**
 * Handle post-processing: move, delete, or keep the bookmark.
 */
async function handleAfterAction(bookmarkId, settings) {
  if (settings.afterAction === "keep") return;

  try {
    if (settings.afterAction === "delete") {
      await chrome.bookmarks.remove(bookmarkId);
      console.log(`[Automate] Bookmark removed after processing.`);
    } else if (settings.afterAction === "move") {
      const folderId = await getOrCreateFolder(settings.processedFolder);
      await chrome.bookmarks.move(bookmarkId, { parentId: folderId });
      console.log(`[Automate] Bookmark moved to ${settings.processedFolder}.`);
    }
  } catch (error) {
    console.warn(`[Automate] Post-processing failed: ${error.message}`);
  }
}

/**
 * Send a bookmark to the webhook endpoint, then clean up.
 */
async function sendBookmark(bookmarkId, bookmark) {
  const settings = await getSettings();

  const payload = {
    url: bookmark.url,
    title: bookmark.title || "",
    folder: bookmark.folder || "",
  };

  try {
    const response = await fetch(settings.webhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      console.log(`[Automate] Bookmark sent: ${bookmark.title || bookmark.url}`);
      await handleAfterAction(bookmarkId, settings);
    } else {
      console.warn(
        `[Automate] Webhook returned ${response.status}: ${await response.text()}`
      );
      // Don't clean up on failure — bookmark stays where it is
    }
  } catch (error) {
    // Sidecar might be down — that's fine, bookmark is still saved in Chrome.
    // It'll get picked up by the daily /bookmarks/list poll as a fallback.
    console.warn(`[Automate] Could not reach webhook: ${error.message}`);
  }
}

/**
 * Listen for new bookmarks.
 * chrome.bookmarks.onCreated fires for both bookmarks and folders.
 * We only care about bookmarks (which have a url property).
 *
 * We also skip bookmarks created inside the processed folder
 * to avoid infinite loops when moving bookmarks around.
 */
chrome.bookmarks.onCreated.addListener(async (id, bookmarkInfo) => {
  // Folders don't have a url — skip them
  if (!bookmarkInfo.url) return;

  // Don't re-process bookmarks that were moved into our processed folder
  const folder = await getFolderPath(bookmarkInfo.parentId);
  const settings = await getSettings();
  if (folder.startsWith(settings.processedFolder)) return;

  await sendBookmark(id, {
    url: bookmarkInfo.url,
    title: bookmarkInfo.title || "",
    folder: folder,
  });
});

console.log("[Automate] Bookmark sync extension loaded.");
