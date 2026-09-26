// Packaged updater smoke app. A separate app ID/name keeps QA registration and
// install files apart from SoundShredder. Never bundled in the real application.
const { app, BrowserWindow, ipcMain } = require('electron');
const fs = require('node:fs'), path = require('node:path');
const { autoUpdater } = require('electron-updater'), { Updates } = require('../updates.cjs');
// NSIS relaunches through Explorer, which does not inherit the test runner's
// environment. Use the private installed location as the persistent fallback.
const home = process.env.SS_UPDATE_QA_HOME || path.resolve(path.dirname(process.execPath), '../profile');
if (!home || !path.isAbsolute(home) || !home.includes(`${path.sep}artifacts${path.sep}electron${path.sep}update-native${path.sep}`)) throw Error('Private QA profile required.');
app.setPath('userData', home);fs.mkdirSync(home, { recursive: true });
let win;
autoUpdater.logger = null;
const service = new Updates({ updater: autoUpdater, version: app.getVersion(), enabled: true,
  prepareInstall: async () => {
    if (fs.existsSync(path.join(home, 'busy'))) throw Error('Simulated active audio job');
    fs.writeFileSync(path.join(home, 'prepared'), app.getVersion());
  } });
service.on('change', state => {
  fs.writeFileSync(path.join(home, 'status.json'), JSON.stringify(state));
  win?.webContents.send('desktop:update-state', state);
});
ipcMain.handle('desktop:update-action', (event, action) => {
  if (event.sender !== win.webContents || event.senderFrame !== win.webContents.mainFrame) throw Error('Untrusted');
  if (action === 'state') return service.snapshot();
  if (['check', 'download', 'install', 'cancel'].includes(action)) void service[action]();
  return service.snapshot();
});
app.whenReady().then(() => {
  fs.writeFileSync(path.join(home, 'pid'), String(process.pid));
  fs.writeFileSync(path.join(home, 'version'), app.getVersion());
  fs.appendFileSync(path.join(home, 'launches'), `${app.getVersion()}\n`);
  win = new BrowserWindow({ width: 620, height: 690, webPreferences: { preload: path.join(__dirname, '../preload.cjs'), contextIsolation: true, sandbox: true, nodeIntegration: false } });
  win.setMenu(null);void win.loadFile(path.join(__dirname, '../updates.html'));void service.check();
});
app.on('window-all-closed', () => app.quit());
