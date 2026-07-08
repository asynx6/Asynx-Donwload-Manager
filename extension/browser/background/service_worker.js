/**
 * AsynxDL Browser Extension — Service Worker (MV3)
 * Intercepts browser downloads, cancels the native Chrome download, and relays
 * the download to the AsynxDL desktop application via the local HTTP API.
 */

const API_HOST = 'http://127.0.0.1:58296';
const API_STATUS = `${API_HOST}/status`;

function isValidUrl(url) {
  return url && (url.startsWith('http://') || url.startsWith('https://'));
}

async function isBackendOnline() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2500);
    const resp = await fetch(API_STATUS, { method: 'GET', signal: controller.signal });
    clearTimeout(timeout);
    return resp.ok;
  } catch (e) {
    return false;
  }
}

async function cancelNativeDownload(itemId) {
  try {
    await chrome.downloads.cancel(itemId);
  } catch (e) {
    console.warn('[AsynxDL] cancel failed', e);
  }
  try {
    await chrome.downloads.erase({ id: itemId });
  } catch (e) {
    // ignore
  }
}

async function storeInterceptedDownload(item) {
  const filename = item.filename || item.url.split('/').pop() || 'unknown';
  const payload = {
    url: item.url,
    filename: filename.replace(/\\/g, '/').split('/').pop(),
    size: item.totalBytes || item.fileSize || 0,
    suggestedSavePath: item.filename || ''
  };
  await chrome.storage.session.set({ asynxdl_intercept: payload });
}

async function openExtensionPopup() {
  try {
    await chrome.action.openPopup();
  } catch (e) {
    chrome.windows.create({
      url: chrome.runtime.getURL('popup/popup.html'),
      type: 'popup',
      width: 380,
      height: 360,
      focused: true
    });
  }
}

chrome.downloads.onCreated.addListener(async (item) => {
  if (!isValidUrl(item.url)) return;
  if (item.state !== 'in_progress') return;

  // Only intercept if the desktop app is running
  if (!(await isBackendOnline())) {
    return;
  }

  await cancelNativeDownload(item.id);
  await storeInterceptedDownload(item);
  await openExtensionPopup();
});

chrome.runtime.onInstalled.addListener(() => {
  // Token tidak diperlukan lagi — langsung ready
  chrome.action.setBadgeText({ text: '' });
});

chrome.action.onClicked.addListener(() => {
  openExtensionPopup();
});
