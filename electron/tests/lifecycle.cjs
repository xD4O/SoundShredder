// Exercise the real Electron window, private Python engine and retained sessions.
const { _electron: electron } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');
const { request } = require('../backend.cjs');
const root = path.resolve(__dirname, '../..');
const home = path.resolve(process.env.SS_TEST_HOME || path.join(root, 'artifacts/electron/QA profile with spaces'));
assert.ok(home.startsWith(path.join(root, 'artifacts') + path.sep), 'Tests must use a workspace artifact profile');
const output = path.join(root, 'artifacts/electron/verification');
fs.mkdirSync(output, { recursive: true });
const executablePath = process.env.SS_TEST_EXECUTABLE || require('electron');
const args = process.env.SS_TEST_EXECUTABLE ? [] : [path.join(root, 'electron')];
const env = { ...process.env, SOUNDSHREDDER_DESKTOP_HOME: home };
delete env.ELECTRON_RUN_AS_NODE;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function waitFor(fn, timeout = 60000) {
  const deadline = Date.now() + timeout;
  let error;
  while (Date.now() < deadline) {
    try { const value = await fn(); if (value) return value; } catch (e) { error = e; }
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
const evidence = { platform: process.platform, architecture: process.arch, executable: executablePath, cycles: [] };
let application;
(async () => {
  for (let cycle = 0; cycle < 4; cycle++) {
    application = await electron.launch({ executablePath, args, env, timeout: 60000 });
    const page = await application.firstWindow();
    await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.setAudioMuted(true));
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const initial = await waitFor(state);
    if (initial.status === 'idle') {
      await page.locator('#start').click();
      console.log('Installing the private CPU engine');
    }
    const ready = await waitFor(async () => {
      const s = await state();
      if (s.status === 'error') throw new Error(s.message);
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
      await page.locator('#results').waitFor({ state: 'visible', timeout: 1200000 });
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
      const nativePid = await application.evaluate(() => process.pid);
      process.kill(nativePid);
    } else if (cycle === 1) {
      await application.evaluate(({ Menu }) => Menu.getApplicationMenu().items[0].submenu.items.find(item => item.label === 'Quit SoundShredder').click()).catch(() => {});
    } else {
      await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].close()).catch(() => {});
    }
    await closing;
    application = null;
    await waitFor(() => !fs.existsSync(path.join(home, 'desktop.json')));
    await assert.rejects(fetch(ready.url + '/api/system'));
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
    await application.close().catch(() => {});
  }
  process.exitCode = 1;
});
