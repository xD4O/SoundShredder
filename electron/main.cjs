'use strict';
const { app, BrowserWindow, Menu, dialog, ipcMain, shell, session, nativeTheme } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { randomUUID } = require('node:crypto');
const { pathToFileURL } = require('node:url');
const { Backend } = require('./backend.cjs');
const { sameOrigin, external, loopback } = require('./security.cjs');
const { readSelection, saveSelection, prepareLocation, contains } = require('./storage.cjs');
const { Updates } = require('./updates.cjs');

const controlHome = path.resolve(process.env.SOUNDSHREDDER_DESKTOP_HOME || (process.platform === 'darwin'
  ? path.join(app.getPath('appData'), 'SoundShredder')
  : path.join(process.env.LOCALAPPDATA || app.getPath('appData'), 'SoundShredder')));
// Keep the Chromium profile and single-instance lock stable across data drives.
app.setPath('userData', path.join(controlHome, 'electron'));
let home = controlHome;
app.setName('SoundShredder');
nativeTheme.themeSource = 'dark';
const root = app.isPackaged ? path.join(process.resourcesPath, 'backend')
  : path.resolve(__dirname, '../artifacts/electron/backend');
const backend = new Backend(root, home);
const welcomeURL = pathToFileURL(path.join(__dirname, 'welcome.html')).href;
const updatesURL = pathToFileURL(path.join(__dirname, 'updates.html')).href;
let updates, updateWindow, updateCheckTimer;
const activeDownloads = new Set();
let win, workspace = null, mode = 'workspace', starting = null, changingStorage = false, pendingQuit = false, quitting = false, permittedExit = false, timer;
let welcomeStatus = 'Opening your sound workspace…';

function trusted(url) { return sameOrigin(url, backend.base) || sameOrigin(url, workspace); }
function alive() { return win && !win.isDestroyed(); }
function focus() { if (alive()) { if (win.isMinimized()) win.restore(); win.show(); win.focus(); } }
function showUpdates() {
  if (updateWindow && !updateWindow.isDestroyed()) { updateWindow.show(); updateWindow.focus(); return; }
  updateWindow = new BrowserWindow({ width: 620, height: 690, minWidth: 450, minHeight: 560,
    parent: alive() ? win : undefined, title: 'SoundShredder updates', backgroundColor: '#090e15', show: false,
    webPreferences: { preload: path.join(__dirname, 'preload.cjs'), sandbox: true, contextIsolation: true, nodeIntegration: false } });
  updateWindow.setMenu(null);
  updateWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  updateWindow.webContents.on('will-navigate', event => event.preventDefault());
  updateWindow.webContents.on('will-attach-webview', event => event.preventDefault());
  updateWindow.once('ready-to-show', () => updateWindow?.show());
  updateWindow.on('closed', () => { updateWindow = null; });
  void updateWindow.loadURL(updatesURL);
  if (['idle', 'current', 'error'].includes(updates?.state.status)) void updates.check();
}
function rendererReady() {
  if (!alive()) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const requestId = randomUUID();
    const done = ready => {
      clearTimeout(timeout);ipcMain.removeListener('desktop:update-ready', reply);
      ready ? resolve() : reject(Error('An upload, save or interface operation is still in progress.'));
    };
    const reply = (event, id, ready) => {
      if (id === requestId && alive() && event.sender === win.webContents && event.senderFrame === win.webContents.mainFrame) done(ready === true);
    };
    const timeout = setTimeout(() => done(false), 3000);
    ipcMain.on('desktop:update-ready', reply);
    win.webContents.send('desktop:prepare-update', requestId);
  });
}
async function prepareUpdate() {
  if (starting || changingStorage || quitting) throw Error('The desktop is busy.');
  quitting = true;
  if (alive()) win.setEnabled(false);
  try {
    if (activeDownloads.size) throw Error('A file download is still in progress.');
    await rendererReady();
    // The engine checks setup and all active audio/export jobs before stopping.
    // Never force-close or cancel processing as a side effect of an update.
    if (backend.child?.exitCode === null && !backend.child.signalCode) {
      if (!backend.base) throw Error('The engine is not ready.');
      await backend.api('/api/stop', {});
    }
    await backend.detach();
    permittedExit = true;
  } catch (error) {
    quitting = false;if (alive()) win.setEnabled(true);throw error;
  }
}
async function recoverUpdate() {
  permittedExit = false;quitting = false;
  if (alive()) win.setEnabled(true);
  if (!backend.child || backend.child.exitCode !== null || backend.child.signalCode) await start();
}
function fail(message) {
  welcomeStatus = message;
  if (!alive()) return;
  win.loadURL(welcomeURL).then(() => win.webContents.send('desktop:status', message)).catch(() => {});
}
async function showSetup() {
  if (changingStorage || quitting) return;
  mode = 'setup';
  if (backend.base && alive()) await win.loadURL(backend.setupURL());
  focus();
}
async function showWorkspace() {
  if (changingStorage || quitting) return;
  mode = 'workspace';
  if (!backend.base) return start();
  const base = backend.base;
  const state = await backend.api('/api/reopen', {});
  if (changingStorage || quitting || backend.base !== base) return;
  if (state.status === 'ready' && loopback(state.url)) {
    workspace = new URL(state.url).origin;
    if (alive() && !sameOrigin(win.webContents.getURL(), workspace)) await win.loadURL(workspace);
  } else if (alive()) await win.loadURL(backend.setupURL());
  focus();
}
async function start() {
  if (changingStorage || quitting) return;
  if (starting) return starting;
  welcomeStatus = 'Opening your sound workspace…';
  starting = (async () => {
    try {
      const selected = await readSelection(controlHome);
      home = backend.home = selected.home;
      backend.managedStorage = selected.managedStorage;
      await backend.start();
      if (!alive() || quitting) return;
      await win.loadURL(backend.setupURL());
      mode = 'workspace';
    } catch (error) { fail(error.message); }
    finally {
      starting = null;
      if (pendingQuit) { pendingQuit = false; void requestQuit(); }
    }
  })();
  return starting;
}
async function requestQuit() {
  if (changingStorage || starting) { pendingQuit = true; return false; }
  if (quitting) return false;
  quitting = true;
  try {
    if (backend.base && backend.child?.exitCode === null && !backend.child.signalCode) {
      const state = await backend.api('/api/state');
      let cancelSetup = state.status === 'cancelling';
      if (['installing', 'starting'].includes(state.status)) {
        const answer = await dialog.showMessageBox(win, { type: 'question', title: 'Setup is still running',
          message: 'Cancel setup and quit SoundShredder?',
          detail: 'Saved sessions are kept. Next time you open the app, you can retry setup to repair any interrupted downloads.',
          buttons: ['Continue setup', 'Cancel setup and quit'], defaultId: 0, cancelId: 0 });
        if (answer.response !== 1) { quitting = false; return false; }
        cancelSetup = true;
      }
      // Cancellation is explicit. Active audio jobs still protect their work.
      await backend.api('/api/stop', { cancel_setup: cancelSetup });
    }
    await backend.detach();
    clearInterval(timer);
    permittedExit = true;
    app.quit();
    return true;
  } catch (error) {
    focus();
    if (!error.statusCode && alive()) {
      const answer = await dialog.showMessageBox(win, { type: 'warning', title: 'The audio engine is not responding',
        message: 'Quit the unresponsive engine?', detail: 'An unfinished job may need to be rerun. Saved sessions will remain.',
        buttons: ['Keep open', 'Quit SoundShredder'], defaultId: 0, cancelId: 0 });
      if (answer.response === 1) {
        await backend.detach(); permittedExit = true; app.quit(); return true;
      }
    } else if (alive()) await dialog.showMessageBox(win, { type: 'info', title: 'SoundShredder is still working',
      message: error.message, detail: 'Cancel setup from its screen, or finish/cancel processing in the workspace, then quit again. Your sessions stay saved.', buttons: ['Keep SoundShredder open'] });
    quitting = false;
    return false;
  }
}
async function chooseStorage() {
  if (changingStorage || starting || quitting) throw Error('Wait for the current operation to finish, then choose a folder.');
  changingStorage = true;
  const previous = { home, managedStorage: backend.managedStorage };
  let stoppedOld = false, committed = false;
  try {
    if (backend.base && backend.child?.exitCode === null && !backend.child.signalCode) {
      const state = await backend.api('/api/state');
      if (['installing', 'starting', 'cancelling'].includes(state.status)) throw Error('Finish or cancel setup before changing its storage folder.');
    }
    const result = await dialog.showOpenDialog(win, { title: 'Choose a location for SoundShredder files',
      message: 'Engines, models and sessions go in a SoundShredder folder here. Existing files stay in their current location.',
      buttonLabel: 'Use this location', defaultPath: path.dirname(home), properties: ['openDirectory', 'createDirectory'] });
    if (result.canceled || !result.filePaths[0]) return { canceled: true };
    const appFolder = app.isPackaged
      ? (process.platform === 'darwin' ? path.resolve(path.dirname(process.execPath), '../..') : path.dirname(process.execPath))
      : app.getAppPath();
    const selected = await prepareLocation(result.filePaths[0], { currentHome: home, protectedPaths: [appFolder, root] });
    if (backend.managedStorage && contains(home, selected.home) && contains(selected.home, home)) return { home };
    if (backend.base && backend.child?.exitCode === null && !backend.child.signalCode) {
      // This endpoint rechecks active audio work before stopping the old engine.
      await backend.api('/api/stop', {});
    }
    stoppedOld = true;
    await backend.detach();
    workspace = null;
    backend.home = selected.home;
    backend.managedStorage = true;
    await backend.start(); // Exclusive ownership must succeed before saving the choice.
    await saveSelection(controlHome, selected.home);
    committed = true;
    home = selected.home;
    mode = 'workspace';
    if (alive()) await win.loadURL(backend.setupURL());
    return { home, freeGiB: selected.freeGiB };
  } catch (error) {
    if (stoppedOld && !committed) {
      try {
        await backend.detach();
        home = backend.home = previous.home;
        backend.managedStorage = previous.managedStorage;
        await backend.start();
        if (alive()) await win.loadURL(backend.setupURL());
      } catch { fail('Storage could not be opened. Reconnect its drive, choose another folder, or select Retry opening. Existing files are kept.'); }
    }
    if (committed) fail('Your storage folder was saved, but its workspace could not open. Select Retry opening.');
    if (alive()) await dialog.showMessageBox(win, { type: 'error', title: committed ? 'Storage selected; workspace could not open' : 'Storage location was not changed',
      message: error.message, detail: 'Existing sessions and downloaded engines have not been moved or deleted.', buttons: ['OK'] });
    return { error: error.message };
  } finally {
    changingStorage = false;
    if (pendingQuit) { pendingQuit = false; void requestQuit(); }
  }
}
function handleExternal(url) {
  if (external(url)) shell.openExternal(url).catch(() => {});
}
async function showWindowsUninstall() {
  const answer = await dialog.showMessageBox(win, { type: 'info', title: 'Uninstall SoundShredder',
    message: 'Remove SoundShredder using Windows Settings',
    detail: 'Finish or cancel processing, then quit SoundShredder. In Windows Settings, search for SoundShredder and choose Uninstall.\n\nSaved sessions, downloaded engines, model caches and exported audio are kept. You can also use Uninstall SoundShredder in the Start menu.',
    buttons: ['Open Windows Settings', 'Cancel'], defaultId: 0, cancelId: 1 });
  if (answer.response === 0) {
    // A fixed native menu action; custom protocols remain blocked in web content.
    try { await shell.openExternal('ms-settings:appsfeatures'); }
    catch { await dialog.showMessageBox(win, { type: 'info', message: 'Open Windows Settings manually',
      detail: 'Go to Apps > Installed apps (Apps & features on Windows 10), search for SoundShredder, and choose Uninstall.', buttons: ['OK'] }); }
  }
}
function createWindow() {
  let bounds = {};
  try { bounds = JSON.parse(fs.readFileSync(path.join(controlHome, 'electron-window.json'), 'utf8')); } catch {}
  win = new BrowserWindow({ width: Math.max(1000, Math.min(1800, Number(bounds.width) || 1380)),
    height: Math.max(700, Math.min(1200, Number(bounds.height) || 900)), minWidth: 900, minHeight: 650,
    title: 'SoundShredder', backgroundColor: '#080c13', show: false,
    icon: path.join(root, 'desktop/icon-256.png'),
    webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true,
      sandbox: true, nodeIntegration: false, webSecurity: true, spellcheck: false } });
  win.once('ready-to-show', () => { win.show(); if (bounds.maximized) win.maximize(); });
  win.on('close', event => {
    if (permittedExit) return;
    event.preventDefault();
    const size = win.getNormalBounds();
    try { fs.writeFileSync(path.join(controlHome, 'electron-window.json'), JSON.stringify({width: size.width, height: size.height, maximized: win.isMaximized()})); } catch {}
    void requestQuit();
  });
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (trusted(url)) void showWorkspace().catch(error => fail(error.message));
    else handleExternal(url);
    return { action: 'deny' };
  });
  win.webContents.on('will-navigate', (event, url) => {
    if (!trusted(url)) { event.preventDefault(); handleExternal(url); }
  });
  win.webContents.on('will-redirect', (event, url) => { if (!trusted(url)) event.preventDefault(); });
  win.webContents.on('will-attach-webview', event => event.preventDefault());
  win.webContents.on('render-process-gone', () => fail('The interface stopped. Select Retry opening to return to your saved workspace.'));
  win.loadURL(welcomeURL);
}
function menu() {
  const actions = [
    { label: 'Workspace', accelerator: 'CmdOrCtrl+1', click: () => void showWorkspace().catch(error => fail(error.message)) },
    { label: 'Setup and diagnostics', accelerator: 'CmdOrCtrl+,', click: () => void showSetup() },
    { label: 'Choose storage folder…', click: () => void chooseStorage().catch(error => fail(error.message)) },
    { type: 'separator' },
    { label: 'Open downloads folder', click: () => void shell.openPath(app.getPath('downloads')) },
    { label: 'Open logs folder', click: () => void shell.openPath(home) },
    ...(process.platform === 'win32' && app.isPackaged
      ? [{ label: 'Uninstall SoundShredder…', click: () => void showWindowsUninstall() }] : []),
    { type: 'separator' },
    { label: 'Quit SoundShredder', accelerator: 'CmdOrCtrl+Q', click: () => void requestQuit() }
  ];
  const template = [{ label: 'SoundShredder', submenu: actions }, { role: 'editMenu' },
    { label: 'View', submenu: [{ role: 'reload' }, { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' }, { role: 'togglefullscreen' }] },
    { label: 'Help', submenu: [
      { label: 'Installation and troubleshooting', click: () => void shell.openPath(path.join(root, 'INSTALLATION.html')) },
      { label: 'GitHub project', click: () => handleExternal('https://github.com/xD4O/SoundShredder') },
      { label: 'Check for Electron updates', click: showUpdates },
      { label: 'About SoundShredder', click: () => dialog.showMessageBox(win, { message: `SoundShredder ${app.getVersion()}`, detail: 'Made by cyr4x · Made for the Higgsfield Community\nLocal audio processing · Electron desktop preview', buttons: ['OK'] }) }
    ] }];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}
function secureSession() {
  const ses = session.defaultSession;
  ses.setPermissionRequestHandler((_wc, permission, callback) => callback(permission === 'clipboard-sanitized-write'));
  ses.setPermissionCheckHandler((_wc, permission, origin) => permission === 'clipboard-sanitized-write' && trusted(origin));
  ses.on('will-download', (_event, item) => {
    if (!trusted(item.getURL())) { item.cancel(); return; }
    activeDownloads.add(item);item.once('done', () => activeDownloads.delete(item));
    item.setSaveDialogOptions({ defaultPath: path.join(app.getPath('downloads'), path.basename(item.getFilename())) });
  });
  ses.webRequest.onBeforeRequest((details, callback) => {
    const localFile = details.url.startsWith(pathToFileURL(__dirname + path.sep).href);
    const blob = details.url.startsWith('blob:') && trusted(details.url.slice(5));
    callback({ cancel: !(trusted(details.url) || localFile || blob || details.url.startsWith('data:')) });
  });
  ses.webRequest.onHeadersReceived((details, callback) => {
    const headers = details.responseHeaders || {};
    if (trusted(details.url)) headers['Content-Security-Policy'] = ["default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; media-src 'self' blob:; connect-src 'self'; object-src 'none'; frame-src 'none'; base-uri 'self'; form-action 'self'"];
    callback({ responseHeaders: headers });
  });
}
for (const [name, handler] of Object.entries({ status: () => welcomeStatus, workspace: showWorkspace, setup: showSetup, storage: chooseStorage,
  updates: showUpdates,
  retry: async () => { if (backend.base && backend.child?.exitCode === null && !backend.child.signalCode) await showWorkspace(); else await start(); }, quit: requestQuit })) {
  ipcMain.handle('desktop:' + name, (event) => {
    if (!alive() || event.sender !== win.webContents || event.senderFrame !== win.webContents.mainFrame ||
        !(trusted(event.senderFrame.url) || event.senderFrame.url === welcomeURL)) throw new Error('Untrusted desktop request.');
    return handler();
  });
}
ipcMain.handle('desktop:update-action', (event, action) => {
  const main = alive() && event.sender === win.webContents && event.senderFrame === win.webContents.mainFrame &&
    (trusted(event.senderFrame.url) || event.senderFrame.url === welcomeURL);
  const panel = updateWindow && !updateWindow.isDestroyed() && event.sender === updateWindow.webContents &&
    event.senderFrame === updateWindow.webContents.mainFrame && event.senderFrame.url === updatesURL;
  if ((!main && !panel) || !updates) throw Error('Untrusted update request.');
  if (action === 'state') return updates.snapshot();
  if (action === 'releases') { handleExternal(updates.state.releaseURL || 'https://github.com/xD4O/SoundShredder/releases'); return; }
  if (!panel || !['check', 'download', 'cancel', 'install'].includes(action)) throw Error('Unsupported update request.');
  // Return immediately; state events keep the controls responsive while work runs.
  void Promise.resolve(updates[action]()).catch(() => {});
  return updates.snapshot();
});
backend.on('exit', ({ code }) => {
  workspace = null;
  if (starting || changingStorage || quitting) return;
  if (code === 0) { permittedExit = true; app.quit(); }
  else fail('The audio engine stopped. Select Retry opening to restart it. Your saved sessions are retained.');
});
if (!app.requestSingleInstanceLock()) { permittedExit = true; app.quit(); }
else {
  // Reopening should focus the current screen, including diagnostics. Starting
  // an asynchronous navigation here can overwrite a user's next menu action.
  app.on('second-instance', focus);
  app.on('activate', focus);
  app.on('before-quit', event => { if (!permittedExit) { event.preventDefault(); void requestQuit(); } });
  app.whenReady().then(async () => {
    const { autoUpdater } = require('electron-updater');
    autoUpdater.logger = null; // Do not log signed download URLs or release contents.
    updates = new Updates({ updater: autoUpdater, version: app.getVersion(), enabled: app.isPackaged,
      arch: process.platform === 'darwin' && app.runningUnderARM64Translation ? 'arm64' : process.arch,
      prepareInstall: prepareUpdate, recoverInstall: recoverUpdate });
    updates.on('change', state => {
      for (const window of [win, updateWindow]) if (window && !window.isDestroyed()) window.webContents.send('desktop:update-state', state);
    });
    secureSession(); createWindow(); menu();
    updateCheckTimer = setTimeout(() => void updates.check(), 8000);
    updateCheckTimer.unref();
    await start();
    let polling = false;
    timer = setInterval(async () => {
      if (polling || quitting || starting || changingStorage || !backend.base || !alive() || backend.child?.exitCode !== null || backend.child?.signalCode) return;
      polling = true;
      const base = backend.base;
      try {
        const state = await backend.api('/api/state');
        if (changingStorage || starting || quitting || backend.base !== base) return;
        if (state.status === 'ready' && loopback(state.url)) {
          workspace = new URL(state.url).origin;
          if (mode === 'workspace' && !sameOrigin(win.webContents.getURL(), workspace)) await win.loadURL(workspace);
        } else if (state.status === 'error' && sameOrigin(win.webContents.getURL(), workspace)) {
          workspace = null; await win.loadURL(backend.setupURL());
        }
      } catch { /* A retry screen is shown by the manager exit handler. */ }
      finally { polling = false; }
    }, 1000);
  }).catch(error => { dialog.showErrorBox('SoundShredder could not open', error.message); permittedExit = true; void backend.detach().finally(() => app.quit()); });
}
