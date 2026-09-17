'use strict';
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('soundshredderDesktop', Object.freeze({
  openWorkspace: () => ipcRenderer.invoke('desktop:workspace'),
  openSetup: () => ipcRenderer.invoke('desktop:setup'),
  retry: () => ipcRenderer.invoke('desktop:retry'),
  quit: () => ipcRenderer.invoke('desktop:quit'),
  onStatus: callback => ipcRenderer.on('desktop:status', (_event, message) => callback(String(message)))
}));
