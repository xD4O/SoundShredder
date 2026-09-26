/* Desktop-only status in the existing sidebar; source/web update checks stay manual. */
(() => {
  const bridge = window.soundshredderDesktop;
  if (!bridge?.onUpdateState) return;
  bridge.onUpdateState(state => {
    const button = document.getElementById('check-updates') || document.getElementById('updates');
    if (!button) return;
    const label = button.querySelector('span') || button;
    label.textContent = state.status === 'available' ? `Update ${state.version} available` :
      state.status === 'downloaded' ? 'Restart & update…' :
      state.status === 'downloading' ? `Downloading update · ${Math.round(state.percent || 0)}%` : 'Desktop updates';
    const help = document.getElementById('update-help') || document.getElementById('update-info');
    if (help) help.textContent = ['available', 'downloaded', 'downloading', 'error', 'unsupported'].includes(state.status)
      ? state.message : 'Checks automatically. Choose when to download and restart.';
  });
})();
