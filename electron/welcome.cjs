const statusText = document.getElementById('status');
window.soundshredderDesktop.onStatus(message => { statusText.textContent = message; });
document.getElementById('retry').onclick = async () => {
  statusText.textContent = 'Opening your sound workspace…';
  try { await window.soundshredderDesktop.retry(); } catch (error) { statusText.textContent = error.message; }
};
document.getElementById('storage').onclick = async () => {
  try {
    const result = await window.soundshredderDesktop.chooseStorage();
    if (result?.error) statusText.textContent = result.error;
  } catch (error) { statusText.textContent = error.message; }
};
