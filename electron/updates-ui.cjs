'use strict';
(() => {
  const $ = id => document.getElementById(id), bridge = window.soundshredderDesktop;
  const bytes = n => Number.isFinite(n) ? `${(n / 1048576).toFixed(1)} MB` : 'Size will appear during download';
  let action = 'check';
  bridge.onUpdateState(state => {
    $('status').textContent = state.status;
    $('message').textContent = state.message;
    $('versions').textContent = `Installed ${state.currentVersion}${state.version ? ` → Available ${state.version}` : ''}`;
    $('size').textContent = state.version ? bytes(state.size) : '';
    $('progress').hidden = !['downloading', 'cancelling'].includes(state.status);
    $('progress').value = state.percent || 0;
    $('transfer').hidden = $('progress').hidden;
    $('transfer').textContent = `${(state.percent || 0).toFixed(0)}% · ${bytes(state.transferred || 0)} downloaded`;
    $('notes').textContent = state.notes || '';
    $('release-notes').hidden = !state.notes;
    action = state.status === 'available' ? 'download' : state.status === 'downloaded' ? 'install' : 'check';
    $('primary').textContent = action === 'download' ? 'Download update' : action === 'install' ? 'Restart & update' : 'Check for updates';
    $('primary').disabled = ['unsupported', 'checking', 'downloading', 'cancelling', 'installing'].includes(state.status);
    $('cancel').hidden = !['downloading', 'cancelling'].includes(state.status);
    $('cancel').disabled = state.status === 'cancelling';
    $('later').disabled = state.status === 'installing';
  });
  async function run(action) {
    try { await bridge.updateAction(action); }
    catch { $('message').textContent = 'Update controls could not respond. Close this panel and retry from Help.'; }
  }
  $('primary').onclick = () => void run(action);
  $('cancel').onclick = () => void run('cancel');
  $('releases').onclick = () => void run('releases');
  $('later').onclick = () => window.close();
})();
