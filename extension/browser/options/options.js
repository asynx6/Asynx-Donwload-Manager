document.addEventListener('DOMContentLoaded', async () => {
  const tokenInput = document.getElementById('token');
  const saveBtn = document.getElementById('save');
  const status = document.getElementById('status');

  const res = await chrome.storage.local.get('token');
  if (res.token) tokenInput.value = res.token;

  saveBtn.addEventListener('click', async () => {
    const token = tokenInput.value.trim();
    if (!token) {
      status.textContent = 'Token cannot be empty.';
      status.style.color = '#c62828';
      return;
    }
    await chrome.storage.local.set({ token });
    chrome.action.setBadgeText({ text: '' });
    status.textContent = 'Token saved successfully.';
    status.style.color = '#2e7d32';
  });
});
