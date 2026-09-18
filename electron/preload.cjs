'use strict';
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('soundshredderDesktop', Object.freeze({
  openWorkspace: () => ipcRenderer.invoke('desktop:workspace'),
  openSetup: () => ipcRenderer.invoke('desktop:setup'),
  chooseStorage: () => ipcRenderer.invoke('desktop:storage'),
  retry: () => ipcRenderer.invoke('desktop:retry'),
  quit: () => ipcRenderer.invoke('desktop:quit'),
  onStatus: callback => {
    ipcRenderer.on('desktop:status', (_event, message) => callback(String(message)));
    // A startup failure can happen before the welcome page finishes loading.
    // Read retained state so recovery never depends on receiving a one-shot event.
    void ipcRenderer.invoke('desktop:status').then(message => callback(String(message))).catch(() => {});
  }
}));
