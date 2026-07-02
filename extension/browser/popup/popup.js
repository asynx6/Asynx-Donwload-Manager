const API_HOST = 'http://127.0.0.1:58296';

let currentData = { url: '', filename: '', size: 0, suggestedSavePath: '' };

async function getToken() {
  const res = await chrome.storage.local.get('token');
  return res.token || '';
}

function formatSize(bytes) {
  if (bytes === 0) return 'Unknown';
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return parseFloat((bytes / Math.pow(1024, i)).toFixed(2)) + ' ' + sizes[i];
}

async function init() {
  const res = await chrome.storage.session.get('asynxdl_intercept');
  const data = res.asynxdl_intercept;
  if (!data) {
    document.getElementById('content').innerHTML = '<p class="error">No intercepted download found.</p>';
    return;
  }
  currentData = data;
  document.getElementById('filename').textContent = data.filename || 'unknown';
  document.getElementById('size').textContent = formatSize(data.size || 0);
  document.getElementById('save-path').textContent = data.suggestedSavePath || 'Downloads';

  document.getElementById('cancel-btn').addEventListener('click', () => {
    chrome.storage.session.remove('asynxdl_intercept');
    window.close();
  });

  document.getElementById('start-btn').addEventListener('click', startDownload);
}

async function startDownload() {
  const token = await getToken();
  if (!token) {
    document.getElementById('error').textContent = 'Token not set. Open extension options.';
    return;
  }
  try {
    const resp = await fetch(`${API_HOST}/downloads/add`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-AsynxDL-Token': token
      },
      body: JSON.stringify({
        url: currentData.url,
        filename: currentData.filename,
        save_path: ''
      })
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(text || 'Backend error');
    }
    chrome.storage.session.remove('asynxdl_intercept');
    document.getElementById('content').classList.add('hidden');
    document.getElementById('success').classList.remove('hidden');
    setTimeout(() => window.close(), 1500);
  } catch (e) {
    document.getElementById('error').textContent = 'Backend tidak merespons';
  }
}

document.addEventListener('DOMContentLoaded', init);
