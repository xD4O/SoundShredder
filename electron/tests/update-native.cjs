// Build/install/upgrade an isolated NSIS QA app through real electron-updater.
// No production release or SoundShredder installation is changed.
const { _electron: electron } = require('playwright');
const { build, Platform, Arch } = require('electron-builder');
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), http = require('node:http');
const { spawn } = require('node:child_process');
const root = path.resolve(__dirname, '../..'), home = path.join(root, 'artifacts/electron/update-native');
const profile = path.join(home, 'profile'), installed = path.join(home, 'installed');
if (process.platform !== 'win32') throw Error('This native upgrade check currently targets Windows NSIS.');
fs.mkdirSync(profile, { recursive: true });
const env = { ...process.env, SS_UPDATE_QA_HOME: profile };delete env.ELECTRON_RUN_AS_NODE;
const executable = path.join(installed, 'SoundShredder Update QA.exe');
for (const name of ['prepared', 'busy', 'version', 'pid']) fs.rmSync(path.join(profile, name), { force: true });
function run(file, args) {
  return new Promise((resolve, reject) => { const child = spawn(file, args, { env, windowsHide: true });
    child.on('error', reject);child.on('exit', code => code === 0 ? resolve() : reject(Error(`QA installer exited ${code}`))); });
}
async function until(fn, milliseconds = 90000) {
  const end = Date.now() + milliseconds;
  while (Date.now() < end) { if (await fn()) return;await new Promise(resolve => setTimeout(resolve, 250)); }
  throw Error('Native updater test timed out.');
}
async function closeOwnedApp() {
  // The installer can relaunch before the QA script writes its new PID. Select
  // only the exact private executable, never the production name or stale PID.
  assert.ok(path.resolve(executable).startsWith(path.resolve(home) + path.sep));
  const escaped = executable.replace(/'/g, "''");
  await run('powershell', ['-NoProfile', '-Command', `$qaProcesses = Get-Process | Where-Object { $_.Path -eq '${escaped}' -and $_.MainWindowHandle -ne 0 }; foreach ($qaProcess in $qaProcesses) { $qaProcess.CloseMainWindow() | Out-Null; $qaProcess.WaitForExit(15000) | Out-Null; if (!$qaProcess.HasExited) { throw 'QA app did not close' } }`]);
}
const feed = path.join(home, 'v2');
const server = http.createServer((req, res) => {
  const name = path.basename(new URL(req.url, 'http://localhost').pathname), file = path.join(feed, name);
  if (!fs.existsSync(file) || !fs.statSync(file).isFile()) { res.writeHead(404);res.end();return; }
  // Full downloads exercise checksum verification; an unsupported Range request
  // makes the updater fall back from differential download to the complete EXE.
  res.setHeader('Content-Length', fs.statSync(file).size);fs.createReadStream(file).pipe(res);
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let application;
  try {
    for (const [folder, version] of [['v1', '0.0.1'], ['v2', '0.0.2']]) {
      const config = { extends: null, appId: 'com.cyr4x.soundshredder.updateqa', productName: 'SoundShredder Update QA',
          extraMetadata: { name: 'soundshredder-update-qa', version, main: 'tests/update-native-app.cjs' },
          directories: { output: path.join(home, folder) },
          files: ['updates.cjs', 'updates.html', 'updates-ui.cjs', 'preload.cjs', 'tests/update-native-app.cjs', 'package.json'], extraResources: [],
          win: { target: ['nsis'], signAndEditExecutable: false, artifactName: 'SoundShredderUpdateQA-${version}-${arch}-Setup.${ext}' },
          nsis: { oneClick: false, perMachine: false, allowElevation: false, allowToChangeInstallationDirectory: true,
            createDesktopShortcut: false, createStartMenuShortcut: false, deleteAppDataOnUninstall: false, runAfterFinish: false },
          npmRebuild: false,
          publish: { provider: 'generic', url: `http://127.0.0.1:${server.address().port}` } };
      const configPath = path.join(home, `${folder}-builder.json`);
      fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
      // An explicit file prevents merging the production GitHub configuration.
      await build({ targets: Platform.WINDOWS.createTarget(['nsis'], Arch.x64), publish: 'never', config: configPath });
      console.log(`Built isolated updater QA ${version}`);
    }
    // Resolve and assert the installation destination before invoking NSIS.
    assert.ok(path.resolve(installed).startsWith(path.resolve(home) + path.sep));
    await run(path.join(home, 'v1/SoundShredderUpdateQA-0.0.1-x64-Setup.exe'), ['/S', `/D=${installed}`]);
    const marker = path.join(profile, 'saved-session-marker');fs.writeFileSync(marker, 'Keep this saved session');
    application = await electron.launch({ executablePath: executable, env, timeout: 60000 });
    const page = await application.firstWindow();
    await page.waitForFunction(() => document.querySelector('#status').textContent === 'available');
    await page.locator('#primary').click();
    await page.waitForFunction(() => document.querySelector('#status').textContent === 'downloaded', null, { timeout: 90000 });
    fs.writeFileSync(path.join(profile, 'busy'), 'Active job');await page.locator('#primary').click();
    await page.waitForFunction(() => document.querySelector('#message').textContent.startsWith('Finish or cancel'));
    assert.equal(fs.existsSync(path.join(profile, 'prepared')), false);
    fs.unlinkSync(path.join(profile, 'busy'));
    const closing = application.waitForEvent('close', { timeout: 90000 });await page.locator('#primary').click();await closing;application = null;
    await until(() => fs.existsSync(path.join(profile, 'version')) && fs.readFileSync(path.join(profile, 'version'), 'utf8') === '0.0.2');
    assert.equal(fs.readFileSync(marker, 'utf8'), 'Keep this saved session');
    await closeOwnedApp();
    fs.writeFileSync(path.join(home, 'verification.json'), JSON.stringify({ from: '0.0.1', to: '0.0.2', retainedProfile: true, busyJobProtected: true, nativeUpgrade: true }, null, 2));
    console.log('Native Windows upgrade passed: real metadata/download/checksum, busy-job protection, NSIS install, automatic relaunch and retained profile.');
  } finally {
    if (application) await application.close();
    await closeOwnedApp();server.close();
    const uninstaller = path.join(installed, 'Uninstall SoundShredder Update QA.exe');
    assert.ok(path.resolve(uninstaller).startsWith(path.resolve(home) + path.sep));
    if (fs.existsSync(uninstaller)) await run(uninstaller, ['/S', `/D=${installed}`]);
  }
})().catch(error => { console.error(error);process.exitCode = 1; });
