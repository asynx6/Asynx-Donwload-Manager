/**
 * AsynxDL Browser Extension — Service Worker (MV3)
 * Intercepts downloads, cancels native Chrome download, and relays to backend.
 */

const API_HOST = 'http://127.0.0.1:58296';

chrome.downloads.onCreated.addListener(async (item) => {
  // Skip jika item tidak memiliki URL/file yang jelas
  if (!item.url || item.url.startsWith('data:') || item.url.startsWith('blob:')) {
    return;
  }
  if (item.state !== 'in_progress') return;

  // Coba ping backend dulu
  let backendOk = false;
  try {
    const resp = await fetch(`${API_HOST}/status`, { method: 'GET', signal: AbortSignal.timeout(3000) });
    backendOk = resp.ok;
  } catch (e) {
    backendOk = false;
  }

  if (!backendOk) {
    // Fallback: biarkan Chrome download secara native
    return;
  }

  // Cancel native download
  try {
    await chrome.downloads.cancel(item.id);
    await chrome.downloads.erase({ id: item.id });
  } catch (e) {
    console.warn('[AsynxDL] cancel native download failed', e);
  }

  // Simpan data ke storage session
  const fileSize = item.totalBytes || item.fileSize || 0;
  const payload = {
    url: item.url,
    filename: item.filename || item.url.split('/').pop() || 'unknown',
    size: fileSize,
    suggestedSavePath: item.filename || ''
  };
  await chrome.storage.session.set({ asynxdl_intercept: payload });

  // Buka popup
  try {
    await chrome.action.openPopup();
  } catch (e) {
    // Fallback: buka popup via window kecil jika openPopup tidak diizinkan
    chrome.windows.create({
      url: chrome.runtime.getURL('popup/popup.html'),
      type: 'popup',
      width: 420,
      height: 340
    });
  }
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get('token', (res) => {
    if (!res.token) {
      chrome.action.setBadgeText({ text: '!' });
      chrome.action.setBadgeBackgroundColor({ color: '#C62828' });
    }
  });
});
