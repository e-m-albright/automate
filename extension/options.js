const DEFAULTS = {
  webhookUrl: "http://localhost:5678/webhook/content",
  afterAction: "move",
  processedFolder: "Automate/Processed",
};

document.addEventListener("DOMContentLoaded", async () => {
  const urlInput = document.getElementById("webhook-url");
  const actionSelect = document.getElementById("after-action");
  const folderInput = document.getElementById("processed-folder");
  const folderField = document.getElementById("folder-field");
  const status = document.getElementById("status");

  // Show/hide folder field based on action
  function updateFolderVisibility() {
    folderField.style.display = actionSelect.value === "move" ? "block" : "none";
  }

  // Load saved settings
  const saved = await chrome.storage.sync.get(Object.keys(DEFAULTS));
  urlInput.value = saved.webhookUrl || DEFAULTS.webhookUrl;
  actionSelect.value = saved.afterAction || DEFAULTS.afterAction;
  folderInput.value = saved.processedFolder || DEFAULTS.processedFolder;
  updateFolderVisibility();

  actionSelect.addEventListener("change", updateFolderVisibility);

  // Save
  document.getElementById("save").addEventListener("click", async () => {
    await chrome.storage.sync.set({
      webhookUrl: urlInput.value.trim() || DEFAULTS.webhookUrl,
      afterAction: actionSelect.value,
      processedFolder: folderInput.value.trim() || DEFAULTS.processedFolder,
    });
    status.textContent = "Saved!";
    setTimeout(() => { status.textContent = ""; }, 2000);
  });
});
