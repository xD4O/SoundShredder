// Full packaged-app update, including the real Python engine and saved media.
// Uses the runner's native application registration: disposable CI hosts only.
'use strict';
const { _electron: electron } = require('playwright');
const { build, Platform, Arch } = require('electron-builder');
const { releaseConfig, normalizedAppleCredentials } = require('../build/notarized.cjs');
const { request } = require('../backend.cjs');
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const os = require('node:os'), http = require('node:http'), crypto = require('node:crypto');
const { spawn } = require('node:child_process');
const asar = require('@electron/asar');
if (process.env.GITHUB_ACTIONS !== 'true' || !process.env.RUNNER_TEMP) throw Error('Full native upgrades run only on disposable GitHub runners.');
const root = path.resolve(__dirname, '../..'), work = path.join(root, 'artifacts/electron/upgrade');
const dist = path.join(root, 'artifacts/electron/dist'), mac = process.platform === 'darwin';
const evidenceDir = path.join(root, 'artifacts/electron/verification');
const previous = JSON.parse(fs.readFileSync(path.join(evidenceDir, 'lifecycle.json')));
const qaControl = path.join(root, 'artifacts/electron/QA profile with spaces');
const selection = fs.readFileSync(path.join(qaControl, 'desktop-storage.json'));
const home = JSON.parse(selection).home;
assert.ok(path.resolve(home).startsWith(path.join(root, 'artifacts') + path.sep));
const control = mac ? path.join(os.homedir(), 'Library/Application Support/SoundShredder') : path.join(process.env.LOCALAPPDATA, 'SoundShredder');
const preference = path.join(control, 'desktop-storage.json');
const savedPreference = fs.existsSync(preference) ? fs.readFileSync(preference) : null;
const installed = mac ? '/Applications/SoundShredder.app' : path.join(work, 'installed');
const exe = mac ? path.join(installed, 'Contents/MacOS/SoundShredder') : path.join(installed, 'SoundShredder.exe');
const env = { ...process.env };delete env.SOUNDSHREDDER_DESKTOP_HOME;delete env.ELECTRON_RUN_AS_NODE;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
let stage = 'starting', engineStatus = null;
function phase(value) { stage = value;console.log('Upgrade check: ' + value); }
async function until(fn, timeout = 90000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { const value = await fn();if (value) return value;await delay(350); }
  throw Error(`Native upgrade check timed out during ${stage}${engineStatus ? ' (engine ' + engineStatus + ')' : ''}.`);
}
function run(file, args, timeout = 180000) {
  return new Promise((resolve, reject) => {
    const child = spawn(file, args, { env, windowsHide: true, stdio: ['ignore','pipe','pipe'] });
    let output = '';child.stdout.on('data', chunk => { output += chunk; });child.stderr.on('data', chunk => { output += chunk; });
    const timer = setTimeout(() => { child.kill();reject(Error('Native tool timed out')); }, timeout);
    child.on('error', error => { clearTimeout(timer);reject(error); });
    child.on('exit', code => { clearTimeout(timer);code === 0 ? resolve(output) : reject(Error(`Native tool exited ${code}: ${output.slice(-1000)}`)); });
  });
}
function instance() {
  const data = JSON.parse(fs.readFileSync(path.join(home, 'desktop.json'))), url = new URL(data.url);
  return { ...data, base: url.origin, token: url.hash.slice(1) };
}
async function ready() {
  return until(async () => {
    try { const i = instance(), s = await request(i.base + '/api/state', i.token);engineStatus = s.status;return s.status === 'ready' && s; }
    catch { return false; }
  }, 180000);
}
function version() {
  const archive = mac ? path.join(installed, 'Contents/Resources/app.asar') : path.join(installed, 'resources/app.asar');
  // Native replacement changes the archive header/offsets at the same path.
  // asar caches that header; a stale one cannot verify the installed version.
  asar.uncache(archive);
  return JSON.parse(asar.extractFile(archive, 'package.json').toString()).version;
}
function digest(file) { return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'); }
const server = http.createServer((req, res) => {
  const name = path.basename(new URL(req.url, 'http://localhost').pathname), file = path.join(dist, name);
  if (!fs.existsSync(file) || !fs.statSync(file).isFile()) { res.writeHead(404);res.end();return; }
  res.setHeader('Content-Length', fs.statSync(file).size);fs.createReadStream(file).pipe(res);
});
let application, page, updateView;
async function launch() {
  application = await electron.launch({ executablePath: exe, env, timeout: 60000 });
  page = await application.firstWindow();
  const s = await ready();await page.waitForURL(url => url.origin === new URL(s.url).origin, { timeout: 60000 });
  await page.locator('#file-input').waitFor({ state: 'attached' });
  return s;
}
async function panel() {
  await application.evaluate((_electron, url) => {
    const updater = process.mainModule.require('electron-updater').autoUpdater;
    globalThis.qaUpdateErrors = [];
    updater.on('error', error => globalThis.qaUpdateErrors.push(error.message));
    updater.setFeedURL({ provider: 'generic', url });
  }, `http://127.0.0.1:${server.address().port}`);
  const opened = application.waitForEvent('window');await page.evaluate(() => window.soundshredderDesktop.openUpdates());
  const view = updateView = await opened;
  await view.waitForFunction(() => ['available','current','error'].includes(document.querySelector('#status').textContent), null, { timeout: 30000 });
  if (await view.locator('#status').textContent() !== 'available') await view.locator('#primary').click();
  await view.waitForFunction(() => document.querySelector('#status').textContent === 'available', null, { timeout: 30000 });
  await view.locator('#primary').click();await view.waitForFunction(() => ['downloaded','error'].includes(document.querySelector('#status').textContent), null, { timeout: 180000 });
  assert.equal(await view.locator('#status').textContent(), 'downloaded', JSON.stringify(await application.evaluate(() => globalThis.qaUpdateErrors)));
  return view;
}
async function close() {
  if (!application) return;
  const closed = application.waitForEvent('close');
  await page.evaluate(() => { void window.soundshredderDesktop.quit(); }).catch(() => {});
  await closed;application = null;
}
(async () => {
  fs.mkdirSync(work, { recursive: true });fs.mkdirSync(control, { recursive: true });
  fs.writeFileSync(preference, selection);
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    assert.ok(!fs.existsSync(installed), 'The native test installation must not already exist.');
    phase('building and installing the test baseline');
    const config = mac ? releaseConfig(process.env) : { extends: path.resolve(__dirname, '../electron-builder.yml') };
    if (mac) Object.assign(process.env, normalizedAppleCredentials(process.env));
    config.extraMetadata = { version: '1.2.99' };
    config.directories = { output: path.join(work, 'baseline') };
    await build({ targets: (mac ? Platform.MAC : Platform.WINDOWS).createTarget(mac ? ['dir'] : ['nsis'], Arch[process.arch]), config, publish: 'never' });
    if (mac) {
      const appDir = fs.readdirSync(config.directories.output).find(name => name === 'mac' || name.startsWith('mac-'));
      await run('/usr/bin/ditto', [path.join(config.directories.output, appDir, 'SoundShredder.app'), installed]);
      await run('/usr/bin/codesign', ['--verify', '--deep', '--strict', installed]);
      await run('/usr/sbin/spctl', ['--assess', '--type', 'execute', installed]);
    } else {
      const installer = fs.readdirSync(config.directories.output).find(name => name.endsWith('-Setup.exe'));
      await run(path.join(config.directories.output, installer), ['/S', `/D=${installed}`]);
    }
    assert.equal(version(), '1.2.99');
    const saved = path.join(home, 'data', previous.session), before = {};
    for (const name of ['request.json', 'source.wav', 'mix.wav']) {
      const file = path.join(saved, name);if (fs.existsSync(file)) before[name] = digest(file);
    }
    assert.ok(before['request.json']);
    phase('launching the baseline and downloading the update');
    await launch();let update = await panel();
    phase('checking Later followed by ordinary Quit');
    await update.locator('#later').click();await close();
    assert.equal(version(), '1.2.99', 'Normal Quit after Later must not install.');
    phase('reopening the baseline and checking pending-save protection');
    await launch();update = await panel();
    await page.evaluate(() => { window.qaAllowUpdate = false;window.soundshredderDesktop.beforeUpdate(() => window.qaAllowUpdate); });
    await update.locator('#primary').click();await update.waitForFunction(() => document.querySelector('#message').textContent.startsWith('Finish or cancel'));
    assert.equal(version(), '1.2.99');await page.evaluate(() => { window.qaAllowUpdate = true; });
    phase('replacing the app and waiting for automatic relaunch');
    const oldManager = instance().pid;
    const closed = application.waitForEvent('close', { timeout: 180000 });await update.locator('#primary').click();await closed;application = null;
    await until(() => { try { return version() === '1.3.0' && instance().pid !== oldManager; } catch { return false; } }, 180000);
    phase('checking the updated engine and retained media');
    const s = await ready();
    const jobs = await (await fetch(s.url + '/api/jobs')).json();assert.ok(jobs.some(job => job.id === previous.session));
    for (const [name, hash] of Object.entries(before)) assert.equal(digest(path.join(saved, name)), hash, name + ' must survive updating');
    assert.equal(fs.readFileSync(preference, 'utf8'), selection.toString());
    const auto = instance();await request(auto.base + '/api/stop', auto.token, {});
    await until(() => !fs.existsSync(path.join(home, 'desktop.json')));await delay(2500);
    phase('reopening the updated application and saved result');
    await launch();assert.equal(await application.evaluate(({app}) => app.getVersion()), '1.3.0');
    const current = await ready();await page.goto(current.url + '/?session=' + previous.session);
    await page.locator('#results').waitFor({ state: 'visible', timeout: 30000 });
    await page.screenshot({ path: path.join(evidenceDir, 'upgraded-workspace.png'), fullPage: true });
    await close();
    if (mac) {
      await run('/usr/bin/codesign', ['--verify','--deep','--strict',installed]);
      await run('/usr/sbin/spctl', ['--assess','--type','execute',installed]);
      await run('/usr/bin/xcrun', ['stapler','validate',installed]);
    }
    fs.writeFileSync(path.join(evidenceDir, 'upgrade.json'), JSON.stringify({ platform: process.platform, arch: process.arch,
      from: '1.2.99', to: '1.3.0', baseline: 'Same candidate code with a test-only older app version',
      native_upgrade: true, later_does_not_install: true, pending_save_protected: true, automatic_relaunch: true,
      saved_session: previous.session, retained_files: Object.keys(before), chosen_storage: home, reopened_result: true,
      signed_gatekeeper_after_upgrade: mac }, null, 2));
    console.log('Full packaged upgrade, Later/quit, pending-save protection, retained real session/storage and relaunch passed.');
  } catch (error) {
    if (page) await page.screenshot({ path: path.join(evidenceDir, 'upgrade-failure.png') }).catch(() => {});
    if (updateView && !updateView.isClosed()) await updateView.screenshot({ path: path.join(evidenceDir, 'upgrade-panel-failure.png') }).catch(() => {});
    throw error;
  } finally {
    await close().catch(() => {});server.closeAllConnections();server.close();
    if (savedPreference) fs.writeFileSync(preference, savedPreference);
    else fs.rmSync(preference, { force: true });
  }
})().catch(error => {
  let message = error.message;
  for (const key of ['CSC_LINK','CSC_KEY_PASSWORD','APPLE_APP_SPECIFIC_PASSWORD']) {
    for (const secret of [process.env[key], process.env[key]?.trim()].filter(Boolean)) message = message.split(secret).join('[redacted]');
  }
  console.error(message);process.exitCode = 1;process.once('exit', () => { process.exitCode = 1; });
});
