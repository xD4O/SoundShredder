'use strict';
const { app, BrowserWindow, Menu, dialog, ipcMain, shell, session } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');
const { Backend } = require('./backend.cjs');
const { sameOrigin, external, loopback } = require('./security.cjs');

const home = path.resolve(process.env.SOUNDSHREDDER_DESKTOP_HOME || (process.platform === 'darwin'
  ? path.join(app.getPath('appData'), 'SoundShredder')
  : path.join(process.env.LOCALAPPDATA || app.getPath('appData'), 'SoundShredder')));
app.setPath('userData', path.join(home, 'electron'));
app.setName('SoundShredder');
const root = app.isPackaged ? path.join(process.resourcesPath, 'backend')
  : path.resolve(__dirname, '../artifacts/electron/backend');
const backend = new Backend(root, home);
const welcomeURL = pathToFileURL(path.join(__dirname, 'welcome.html')).href;
let win, workspace = null, mode = 'workspace', starting = null, quitting = false, permittedExit = false, timer;

function trusted(url) { return sameOrigin(url, backend.base) || sameOrigin(url, workspace); }
function alive() { return win && !win.isDestroyed(); }
function focus() { if (alive()) { if (win.isMinimized()) win.restore(); win.show(); win.focus(); } }
function fail(message) {
  if (!alive()) return;
  win.loadURL(welcomeURL).then(() => win.webContents.send('desktop:status', message)).catch(() => {});
}
async function showSetup() {
  mode = 'setup';
  if (backend.base && alive()) await win.loadURL(backend.setupURL());
  focus();
}
async function showWorkspace() {
  mode = 'workspace';
  if (!backend.base) return start();
  const state = await backend.api('/api/reopen', {});
  if (state.status === 'ready' && loopback(state.url)) {
    workspace = new URL(state.url).origin;
    if (alive() && !sameOrigin(win.webContents.getURL(), workspace)) await win.loadURL(workspace);
  } else if (alive()) await win.loadURL(backend.setupURL());
  focus();
}
async function start() {
  if (starting) return starting;
  starting = (async () => {
    try {
      await backend.start();
      if (!alive() || quitting) return;
      await win.loadURL(backend.setupURL());
      mode = 'workspace';
    } catch (error) { fail(error.message); }
    finally { starting = null; }
  })();
  return starting;
}
async function requestQuit() {
  if (quitting) return false;
  quitting = true;
  try {
    if (backend.base && backend.child?.exitCode === null && !backend.child.signalCode) {
      // The manager refuses to stop during setup or an active audio job.
      await backend.api('/api/stop', {});
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
      message: error.message, detail: 'Finish setup, or finish/cancel processing in the workspace, then quit again. Your sessions stay saved.', buttons: ['Keep SoundShredder open'] });
    quitting = false;
    return false;
  }
}
function handleExternal(url) {
  if (external(url)) shell.openExternal(url).catch(() => {});
}
function createWindow() {
  let bounds = {};
  try { bounds = JSON.parse(fs.readFileSync(path.join(home, 'electron-window.json'), 'utf8')); } catch {}
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
    try { fs.writeFileSync(path.join(home, 'electron-window.json'), JSON.stringify({width: size.width, height: size.height, maximized: win.isMaximized()})); } catch {}
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
    { type: 'separator' },
    { label: 'Open downloads folder', click: () => void shell.openPath(app.getPath('downloads')) },
    { label: 'Open logs folder', click: () => void shell.openPath(home) },
    { type: 'separator' },
    { label: 'Quit SoundShredder', accelerator: 'CmdOrCtrl+Q', click: () => void requestQuit() }
  ];
  const template = [{ label: 'SoundShredder', submenu: actions }, { role: 'editMenu' },
    { label: 'View', submenu: [{ role: 'reload' }, { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' }, { role: 'togglefullscreen' }] },
    { label: 'Help', submenu: [
      { label: 'Installation and troubleshooting', click: () => void shell.openPath(path.join(root, 'INSTALLATION.html')) },
      { label: 'GitHub project', click: () => handleExternal('https://github.com/xD4O/SoundShredder') },
      { label: 'Check for Electron updates', click: () => handleExternal('https://github.com/xD4O/SoundShredder/releases') },
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
for (const [name, handler] of Object.entries({ workspace: showWorkspace, setup: showSetup,
  retry: async () => { if (backend.base && backend.child?.exitCode === null && !backend.child.signalCode) await showWorkspace(); else await start(); }, quit: requestQuit })) {
  ipcMain.handle('desktop:' + name, (event) => {
    if (!alive() || event.sender !== win.webContents || event.senderFrame !== win.webContents.mainFrame ||
        !(trusted(event.senderFrame.url) || event.senderFrame.url === welcomeURL)) throw new Error('Untrusted desktop request.');
    return handler();
  });
}
backend.on('exit', ({ code }) => {
  workspace = null;
  if (starting || quitting) return;
  if (code === 0) { permittedExit = true; app.quit(); }
  else fail('The audio engine stopped. Select Retry opening to restart it. Your saved sessions are retained.');
});
if (!app.requestSingleInstanceLock()) { permittedExit = true; app.quit(); }
else {
  app.on('second-instance', () => { focus(); if (!starting && backend.base) void showWorkspace().catch(error => fail(error.message)); });
  app.on('activate', focus);
  app.on('before-quit', event => { if (!permittedExit) { event.preventDefault(); void requestQuit(); } });
  app.whenReady().then(async () => {
    secureSession(); createWindow(); menu(); await start();
    let polling = false;
    timer = setInterval(async () => {
      if (polling || quitting || starting || !backend.base || !alive() || backend.child?.exitCode !== null || backend.child?.signalCode) return;
      polling = true;
      try {
        const state = await backend.api('/api/state');
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
