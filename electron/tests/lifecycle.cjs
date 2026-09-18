// Exercise the real Electron window, private Python engine and retained sessions.
const { _electron: electron } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');
const { request } = require('../backend.cjs');
const root = path.resolve(__dirname, '../..');
const controlHome = path.resolve(process.env.SS_TEST_HOME || path.join(root, 'artifacts/electron/QA profile with spaces'));
const preference = path.join(controlHome, 'desktop-storage.json');
let home = fs.existsSync(preference) ? JSON.parse(fs.readFileSync(preference)).home : controlHome;
for (const folder of [controlHome, home]) assert.ok(folder.startsWith(path.join(root, 'artifacts') + path.sep), 'Tests must use a workspace artifact profile');
const output = path.join(root, 'artifacts/electron/verification');
fs.mkdirSync(output, { recursive: true });
const executablePath = process.env.SS_TEST_EXECUTABLE || require('electron');
const args = process.env.SS_TEST_EXECUTABLE ? [] : [path.join(root, 'electron')];
const env = { ...process.env, SOUNDSHREDDER_DESKTOP_HOME: controlHome };
delete env.ELECTRON_RUN_AS_NODE;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function waitFor(fn, timeout = 60000) {
  const deadline = Date.now() + timeout;
  let error;
  while (Date.now() < deadline) {
    try { const value = await fn(); if (value) return value; } catch (e) { if (e.fatal) throw e; error = e; }
    await delay(400);
  }
  throw new Error('Timed out: ' + (error?.message || fn.toString()));
}
function instance() {
  const metadata = JSON.parse(fs.readFileSync(path.join(home, 'desktop.json'), 'utf8'));
  const u = new URL(metadata.url);
  return { ...metadata, base: u.origin, token: u.hash.slice(1) };
}
async function state() { const i = instance(); return request(i.base + '/api/state', i.token); }
const evidence = { platform: process.platform, architecture: process.arch, executable: executablePath,
  custom_storage: home !== controlHome, cycles: [] };
let application, nativePid;
async function verifySetupCancellation() {
  if (fs.existsSync(path.join(home, 'settings.json'))) return;
  application = await electron.launch({ executablePath, args, env, timeout: 60000 });
  let page = await application.firstWindow();
  nativePid = await application.evaluate(() => process.pid);
  const initial = await waitFor(state);
  assert.equal(initial.status, 'idle', 'A fresh QA profile must offer setup');
  const chosen = path.join(root, 'artifacts/electron/Chosen engine storage');
  fs.mkdirSync(chosen, { recursive: true });
  await application.evaluate(({ dialog }, folder) => {
    dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [folder] });
  }, chosen);
  await page.locator('#choose-storage').click();
  await waitFor(() => fs.existsSync(preference));
  home = JSON.parse(fs.readFileSync(preference)).home;
  assert.equal(home, fs.realpathSync(path.join(chosen, 'SoundShredder')));
  await waitFor(async () => (await state()).models_home === path.join(home, 'models'));
  evidence.custom_storage = true;
  const waitInstalling = () => waitFor(async () => {
    const s = await state();
    if (s.status === 'error') throw Object.assign(new Error(s.message), { fatal: true });
    return s.status === 'installing' && s.progress >= 20 && s;
  }, 120000);
  await page.locator('#start').click();
  await waitInstalling();
  await page.locator('#cancel').waitFor({ state: 'visible' });
  await page.locator('#diagnostics').click();
  await page.locator('#log').waitFor();
  await page.screenshot({ path: path.join(output, 'setup-progress.png'), fullPage: true });
  await application.evaluate(({ dialog, BrowserWindow }) => {
    globalThis.qaQuitMessage = null;
    dialog.showMessageBox = async (_window, options) => { globalThis.qaQuitMessage = options.message; return { response: 0 }; };
    BrowserWindow.getAllWindows()[0].close();
  });
  await waitFor(() => application.evaluate(() => globalThis.qaQuitMessage));
  assert.match(await application.evaluate(() => globalThis.qaQuitMessage), /Cancel setup and quit/);
  assert.ok(['installing', 'starting'].includes((await state()).status));
  await page.locator('#cancel').click();
  await waitFor(async () => (await state()).status === 'idle');
  assert.ok(fs.existsSync(path.join(home, 'setup-interrupted.json')));
  await page.locator('#start').click();
  await waitInstalling();
  const closing = application.waitForEvent('close');
  await application.evaluate(({ dialog, BrowserWindow }) => {
    dialog.showMessageBox = async () => ({ response: 1 });
    BrowserWindow.getAllWindows()[0].close();
  });
  await closing; application = null;
  await waitFor(() => !fs.existsSync(path.join(home, 'desktop.json')));
  assert.ok(fs.existsSync(path.join(home, 'setup-interrupted.json')));
  // The normal first cycle reopens this interrupted profile and repairs setup.
  evidence.setup_cancel_retry_and_native_quit = true;
  console.log('Verified setup cancellation, retry, Continue setup and cancel-and-quit');
}
(async () => {
  await verifySetupCancellation();
  for (let cycle = 0; cycle < 4; cycle++) {
    application = await electron.launch({ executablePath, args, env, timeout: 60000 });
    const page = await application.firstWindow();
    nativePid = await application.evaluate(() => process.pid);
    await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.setAudioMuted(true));
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const initial = await waitFor(state);
    if (cycle === 0 && evidence.setup_cancel_retry_and_native_quit) {
      assert.equal(initial.status, 'idle', 'Interrupted setup must wait for an explicit retry');
    }
    if (initial.status === 'idle') {
      await page.locator('#start').click();
      console.log('Installing the private CPU engine');
    }
    const ready = await waitFor(async () => {
      const s = await state();
      if (s.status === 'error') throw Object.assign(new Error(s.message), { fatal: true });
      return s.status === 'ready' && s;
    }, 1200000);
    await page.waitForURL(url => url.origin === new URL(ready.url).origin, { timeout: 60000 });
    await page.locator('#file-input').waitFor({ state: 'attached' });
    assert.equal(await page.evaluate(() => typeof require), 'undefined');
    assert.equal(await page.evaluate(() => typeof process), 'undefined');
    const prefs = await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences());
    assert.ok(prefs.sandbox && prefs.contextIsolation && !prefs.nodeIntegration);
    const pid = instance().pid;
    const duplicate = spawn(executablePath, args, { env, windowsHide: true, stdio: 'ignore' });
    await new Promise((resolve, reject) => { duplicate.on('exit', code => code === 0 ? resolve() : reject(new Error('Duplicate launch failed'))); duplicate.on('error', reject); });
    assert.equal(instance().pid, pid);
    assert.equal(await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().length), 1);
    if (process.platform === 'darwin' && process.env.SS_TEST_EXECUTABLE) {
      const bundle = path.resolve(executablePath, '../../..');
      const opened = spawnSync('/usr/bin/open', ['-a', bundle], { env, timeout: 15000 });
      assert.equal(opened.status, 0, opened.stderr?.toString());
      assert.equal(instance().pid, pid);
      evidence.mac_launch_services_reopen = true;
    }
    await page.evaluate(() => { void window.soundshredderDesktop.openSetup(); });
    await page.locator('#diagnostics').click();
    await page.locator('#log').waitFor();
    await page.evaluate(() => { void window.soundshredderDesktop.openWorkspace(); });
    await page.locator('#file-input').waitFor({ state: 'attached' });
    if (cycle === 0) {
      const video = path.join(output, 'Electron QA footage.mp4');
      const runtime = process.platform === 'darwin' ? path.join(home, 'runtimes', 'py311-macos-' + (process.arch === 'arm64' ? 'arm64' : 'x86_64') + '-cpu', 'bin/python3.11') : path.join(home, 'runtimes/py313-cpu/python.exe');
      const generated = spawnSync(runtime, ['-c', 'import imageio_ffmpeg,subprocess,sys; subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),"-y","-f","lavfi","-i","color=c=0x173f3c:s=320x180:d=1","-f","lavfi","-i","sine=frequency=440:duration=1","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",sys.argv[1]],check=True)', video], { timeout: 30000, windowsHide: true });
      assert.equal(generated.status, 0, generated.stderr?.toString());
      await page.locator('#file-input').setInputFiles(video);
      await page.locator('#video-panel').waitFor({ state: 'visible' });
      await page.locator('#show-video').uncheck();
      await page.locator('#video-body').waitFor({ state: 'hidden' });
      await page.locator('#show-video').check();
      await page.locator('#video-body').waitFor({ state: 'visible' });
      await page.locator('#video-play').click();
      await waitFor(() => page.locator('#footage').evaluate(video => video.currentTime > 0));
      evidence.video_preview_and_toggle = true;
      await page.locator('#device').selectOption('cpu');
      await page.locator('#separate').click();
      await waitFor(async () => (await (await fetch(ready.url + '/api/system')).json()).active_jobs.length);
      // Capture the native refusal instead of displaying a blocking QA dialog.
      await application.evaluate(({ dialog, BrowserWindow }) => {
        globalThis.qaOriginalDialog = dialog.showMessageBox;
        globalThis.qaQuitMessage = null;
        dialog.showMessageBox = async (_window, options) => { globalThis.qaQuitMessage = options.message; return { response: 0 }; };
        BrowserWindow.getAllWindows()[0].close();
      });
      await waitFor(() => application.evaluate(() => globalThis.qaQuitMessage));
      assert.match(await application.evaluate(() => globalThis.qaQuitMessage), /Finish or cancel/);
      await application.evaluate(({ dialog }) => { dialog.showMessageBox = globalThis.qaOriginalDialog; });
      assert.equal(instance().pid, pid);
      evidence.active_job_quit_protected = true;
      console.log('Running real CPU separation');
      let lastProgress = '';
      await waitFor(async () => {
        const jobs = await (await fetch(ready.url + '/api/jobs')).json();
        const job = jobs.find(job => job.filename === 'Electron QA footage.mp4');
        if (!job) return false;
        const message = `${job.status}: ${job.message || ''}`;
        if (message !== lastProgress) { console.log(message); lastProgress = message; }
        if (['failed', 'cancelled'].includes(job.status)) throw Object.assign(new Error(message), { fatal: true });
        return job.status === 'complete';
      }, 1200000);
      await page.locator('#results').waitFor({ state: 'visible', timeout: 30000 });
      evidence.session = new URL(page.url()).searchParams.get('session');
      assert.match(evidence.session, /^[a-f0-9]{32}$/);
      await page.locator('#listening-panel').waitFor({ state: 'visible' });
      const downloadPath = path.join(output, 'cleaned.wav');
      await application.evaluate(({ session }, savePath) => {
        session.defaultSession.once('will-download', (_event, item) => item.setSavePath(savePath));
      }, downloadPath);
      await page.locator('#download-mix').click();
      await waitFor(() => fs.existsSync(downloadPath) && fs.statSync(downloadPath).size > 44);
      await page.screenshot({ path: path.join(output, 'workspace.png'), fullPage: true });
      evidence.actual_cpu_separation_and_download = true;
      if (evidence.custom_storage) {
        const modelCache = path.join(home, 'models/bandit-infer');
        assert.ok(fs.readdirSync(modelCache, { recursive: true }).some(file => {
          const stat = fs.statSync(path.join(modelCache, file));
          return stat.isFile() && stat.size > 400_000_000;
        }), 'The real separation checkpoint must download to the chosen drive');
        assert.ok(fs.existsSync(path.join(home, 'data', evidence.session)));
        assert.ok(fs.existsSync(path.join(home, 'temp')));
        evidence.engine_models_sessions_in_chosen_folder = true;
      }
    } else {
      const jobs = await page.evaluate(async () => (await fetch('/api/jobs')).json());
      assert.ok(jobs.some(job => job.id === evidence.session), 'The saved session must survive quitting');
    }
    assert.deepEqual(errors, [], 'No renderer errors');
    // Exercise window Close and menu Quit, not just API shutdown.
    const closing = application.waitForEvent('close');
    if (cycle === 2) {
      // Playwright may launch through a Windows command shim. Kill the actual
      // Electron main process, not that shim, to exercise owner-pipe cleanup.
      process.kill(nativePid);
    } else if (cycle === 1) {
      await application.evaluate(({ Menu }) => Menu.getApplicationMenu().items[0].submenu.items.find(item => item.label === 'Quit SoundShredder').click()).catch(() => {});
    } else {
      await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].close()).catch(() => {});
    }
    await closing;
    application = null;
    if (cycle === 2) {
      // Windows may terminate the whole process job before Python can unlink
      // metadata. The next launch must recover that stale file via the OS lock.
      await waitFor(() => { try { process.kill(pid, 0); return false; } catch { return true; } });
    } else await waitFor(() => !fs.existsSync(path.join(home, 'desktop.json')));
    await waitFor(async () => {
      try { await fetch(ready.url + '/api/system', { signal: AbortSignal.timeout(2000) }); return false; }
      catch { return true; }
    });
    evidence.cycles.push({ cycle: cycle + 1, manager_pid: pid, duplicate_launch: true, sessions_retained: true, close: cycle === 2 ? 'host-crash' : cycle === 1 ? 'native-menu' : 'window', engine_stopped: true });
    console.log('Verified close/reopen cycle ' + (cycle + 1));
  }
  fs.writeFileSync(path.join(output, 'lifecycle.json'), JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify(evidence, null, 2));
})().catch(async error => {
  console.error(error);
  if (application) {
    try { await (await application.firstWindow()).screenshot({ path: path.join(output, 'failure.png'), fullPage: true }); } catch {}
    try { const i = instance(); await request(i.base + '/api/stop', i.token, {}); } catch {}
    try { process.kill(nativePid); } catch {}
    await Promise.race([application.close().catch(() => {}), delay(5000)]);
  }
  process.exit(1);
});
