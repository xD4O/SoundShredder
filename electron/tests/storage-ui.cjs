// Test real native folder-picker results, persistence, and recovery with private
// QA profiles. No real user profile or installation is moved or deleted.
const { _electron: electron } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { Backend, request } = require('../backend.cjs');
const root = path.resolve(__dirname, '../..');
const output = path.join(root, 'artifacts/electron/verification');
const qa = fs.mkdtempSync(path.join(root, 'artifacts/electron/Storage picker QA '));
const control = path.join(qa, 'Control', 'SoundShredder');
const firstDrive = path.join(qa, 'Chosen drive with spaces');
const secondDrive = path.join(qa, 'Second drive');
for (const folder of [control, firstDrive, secondDrive, output]) fs.mkdirSync(folder, { recursive: true });
const first = path.join(firstDrive, 'SoundShredder');
const preference = path.join(control, 'desktop-storage.json');
fs.mkdirSync(path.join(control, 'data'));
fs.writeFileSync(path.join(control, 'data/original.wav'), 'keep the old audio');
const executablePath = process.env.SS_TEST_EXECUTABLE || require('electron');
const args = process.env.SS_TEST_EXECUTABLE ? [] : [path.join(root, 'electron')];
const env = { ...process.env, SOUNDSHREDDER_DESKTOP_HOME: control }; delete env.ELECTRON_RUN_AS_NODE;
let application, page, home = control, errors = [], otherOwner;
async function waitFor(fn, timeout = 30000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { try { if (await fn()) return; } catch {} await new Promise(r => setTimeout(r, 100)); }
  throw Error('Storage UI test timed out: ' + fn.toString());
}
function instance() {
  const saved = JSON.parse(fs.readFileSync(path.join(home, 'desktop.json'))), url = new URL(saved.url);
  return { pid: saved.pid, base: url.origin, token: url.hash.slice(1) };
}
async function state() { const i = instance(); return request(i.base + '/api/state', i.token); }
async function launch() {
  application = await electron.launch({ executablePath, args, env, timeout: 60000 });
  page = await application.firstWindow();
  page.on('pageerror', error => errors.push(error.message));
  await application.evaluate(({ dialog }) => {
    globalThis.qaStorageMessages = [];
    dialog.showMessageBox = async (...args) => { globalThis.qaStorageMessages.push(args.at(-1).message); return { response: 0 }; };
  });
}
async function select(folder, selector = '#choose-storage') {
  await application.evaluate(({ dialog }, chosen) => {
    dialog.showOpenDialog = async () => ({ canceled: !chosen, filePaths: chosen ? [chosen] : [] });
  }, folder);
  await page.locator(selector).click();
}
async function close() {
  const closed = application.waitForEvent('close', { timeout: 45000 });
  await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].close());
  await closed; application = null;
  await waitFor(() => !fs.existsSync(path.join(home, 'desktop.json')));
}
(async () => {
  await launch(); await waitFor(async () => (await state()).status === 'idle');
  const originalPid = instance().pid;
  await select(null);
  await waitFor(() => page.locator('#choose-storage').isEnabled());
  assert.equal(instance().pid, originalPid);
  assert.equal(fs.existsSync(preference), false);
  const appPaths = await application.evaluate(({ app }) => ({ packaged: app.isPackaged,
    executable: process.execPath, resources: process.resourcesPath, appPath: app.getAppPath() }));
  const appFolder = appPaths.packaged ? path.dirname(appPaths.executable) : appPaths.appPath;
  await select(appFolder);
  await waitFor(() => application.evaluate(() => globalThis.qaStorageMessages.length > 0));
  assert.match(await application.evaluate(() => globalThis.qaStorageMessages.at(-1)), /separate from the installed/);
  assert.equal(instance().pid, originalPid);
  await select(firstDrive);
  await waitFor(() => fs.existsSync(preference));
  home = JSON.parse(fs.readFileSync(preference)).home;
  assert.equal(home, fs.realpathSync(first));
  await waitFor(async () => (await state()).home === home);
  assert.equal((await state()).models_home, path.join(home, 'models'));
  await page.locator('#choose-storage').waitFor();
  await page.screenshot({ path: path.join(output, 'storage-selected.png'), fullPage: true });
  assert.equal(await page.locator('#storage').textContent().then(text => text.includes(home)), true);
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.screenshot({ path: path.join(output, 'storage-narrow.png'), fullPage: true });
  await page.setViewportSize({ width: 1364, height: 835 });
  fs.mkdirSync(path.join(home, 'data'));
  fs.writeFileSync(path.join(home, 'data/original.wav'), 'keep the selected audio');
  // A second, independently owned profile must not be taken over. Restore the
  // original manager and preference when that folder cannot be acquired.
  const busyHome = path.join(qa, 'Already running', 'SoundShredder');
  fs.mkdirSync(busyHome, { recursive: true });
  const backendRoot = appPaths.packaged ? path.join(appPaths.resources, 'backend')
    : path.resolve(appPaths.appPath, '../artifacts/electron/backend');
  otherOwner = new Backend(backendRoot, busyHome, true);
  await otherOwner.start();
  await application.evaluate(() => { globalThis.qaStorageMessages = []; });
  await select(busyHome);
  await waitFor(() => application.evaluate(() => globalThis.qaStorageMessages.length > 0));
  assert.equal(JSON.parse(fs.readFileSync(preference)).home, home);
  await waitFor(async () => (await state()).home === home);
  assert.equal((await otherOwner.api('/api/state')).home, busyHome);
  await otherOwner.api('/api/stop', {}); await otherOwner.detach(); otherOwner = null;
  await close();
  await launch(); await waitFor(async () => (await state()).home === home);
  const pid = instance().pid;
  const duplicate = spawn(executablePath, args, { env, windowsHide: true, stdio: 'ignore' });
  await new Promise((resolve, reject) => { duplicate.on('exit', code => code === 0 ? resolve() : reject(Error('Duplicate launch failed'))); duplicate.on('error', reject); });
  assert.equal(instance().pid, pid, 'Folder changes must retain one global desktop instance');
  await close();
  const offline = path.join(firstDrive, 'Temporarily disconnected');
  assert.ok(fs.realpathSync(first).startsWith(fs.realpathSync(qa) + path.sep));
  assert.ok(path.resolve(offline).startsWith(fs.realpathSync(qa) + path.sep));
  fs.renameSync(first, offline);
  await launch();
  await waitFor(async () => /Reconnect/.test(await page.locator('#status').textContent()));
  assert.equal(fs.existsSync(first), false, 'Do not recreate an offline drive path');
  await page.screenshot({ path: path.join(output, 'storage-offline-recovery.png') });
  await select(secondDrive, '#storage');
  await waitFor(() => JSON.parse(fs.readFileSync(preference)).home !== home);
  home = JSON.parse(fs.readFileSync(preference)).home;
  await waitFor(async () => (await state()).home === home);
  fs.renameSync(offline, first);
  await select(first);
  await waitFor(() => JSON.parse(fs.readFileSync(preference)).home === fs.realpathSync(first));
  home = fs.realpathSync(first);
  await waitFor(async () => (await state()).home === home);
  assert.equal(fs.readFileSync(path.join(home, 'data/original.wav'), 'utf8'), 'keep the selected audio');
  assert.equal(fs.readFileSync(path.join(control, 'data/original.wav'), 'utf8'), 'keep the old audio');
  assert.deepEqual(errors, []);
  await close();
  const evidence = { platform: process.platform, native_picker_cancel: true, rejects_app_folder: true,
    choice_persists: true, models_and_temp_follow_choice: fs.existsSync(path.join(home, 'temp')),
    duplicate_instance_prevented: true, busy_profile_rollback: true, narrow_layout: true,
    offline_drive_recovery: true, switch_back_preserves_audio: true, renderer_errors: errors };
  fs.writeFileSync(path.join(output, 'storage-ui.json'), JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify(evidence));
})().catch(async error => {
  console.error(error); process.exitCode = 1;
  if (page) await page.screenshot({ path: path.join(output, 'storage-failure.png') }).catch(() => {});
}).finally(async () => {
  if (otherOwner) await otherOwner.detach();
  if (application) {
    await application.evaluate(({ app }) => app.exit(1)).catch(() => {});
    await application.close().catch(() => {});
  }
});
