'use strict';
const { contextBridge, ipcRenderer } = require('electron');
const updateGuards = new Set();
ipcRenderer.on('desktop:prepare-update', (_event, requestId) => {
  let ready = false;
  try { ready = [...updateGuards].every(guard => guard() === true); } catch {}
  ipcRenderer.send('desktop:update-ready', requestId, ready);
});
contextBridge.exposeInMainWorld('soundshredderDesktop', Object.freeze({
  beforeUpdate: guard => { updateGuards.add(guard); return () => updateGuards.delete(guard); },
  openWorkspace: () => ipcRenderer.invoke('desktop:workspace'),
  openSetup: () => ipcRenderer.invoke('desktop:setup'),
  chooseStorage: () => ipcRenderer.invoke('desktop:storage'),
  retry: () => ipcRenderer.invoke('desktop:retry'),
  quit: () => ipcRenderer.invoke('desktop:quit'),
  openUpdates: () => ipcRenderer.invoke('desktop:updates'),
  updateAction: action => ipcRenderer.invoke('desktop:update-action', action),
  onUpdateState: callback => {
    const handler = (_event, state) => callback(state);
    ipcRenderer.on('desktop:update-state', handler);
    void ipcRenderer.invoke('desktop:update-action', 'state').then(callback).catch(() => {});
    return () => ipcRenderer.removeListener('desktop:update-state', handler);
  },
  onStatus: callback => {
    ipcRenderer.on('desktop:status', (_event, message) => callback(String(message)));
    // A startup failure can happen before the welcome page finishes loading.
    // Read retained state so recovery never depends on receiving a one-shot event.
    void ipcRenderer.invoke('desktop:status').then(message => callback(String(message))).catch(() => {});
  }
}));
