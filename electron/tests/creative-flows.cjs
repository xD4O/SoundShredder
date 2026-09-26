// Exercise prompt encoding, repeated cleanup and the Lab in the packaged engine.
// Reuses only the disposable media/profile created by lifecycle.cjs.
'use strict';
const { _electron: electron } = require('playwright');
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const { spawnSync } = require('node:child_process');
const { request } = require('../backend.cjs');
const root = path.resolve(__dirname, '../..'), output = path.join(root, 'artifacts/electron/verification');
const control = path.join(root, 'artifacts/electron/QA profile with spaces');
const home = JSON.parse(fs.readFileSync(path.join(control, 'desktop-storage.json'))).home;
assert.ok(path.resolve(home).startsWith(path.join(root, 'artifacts') + path.sep));
const session = JSON.parse(fs.readFileSync(path.join(output, 'lifecycle.json'))).session;
const env = { ...process.env, SOUNDSHREDDER_DESKTOP_HOME: control };delete env.ELECTRON_RUN_AS_NODE;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(fn, timeout = 90000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { const value = await fn();if (value) return value;await delay(300); }
  throw Error('Packaged creative workflow timed out.');
}
let app, page, base;
function instance() {
  const data = JSON.parse(fs.readFileSync(path.join(home, 'desktop.json'))), url = new URL(data.url);
  return { base: url.origin, token: url.hash.slice(1) };
}
async function api(route, payload, method = 'POST') {
  const response = await fetch(base + route, payload === undefined ? {} : {
    method, headers: { 'Content-Type': 'application/json', Origin: base }, body: JSON.stringify(payload),
  });
  const data = await response.json();assert.ok(response.ok, JSON.stringify(data));return data;
}
const route = `/api/jobs/${session}/lab`;
async function action(operation, payload = {}) {
  const current = await api(route);
  await api(route + '/actions/' + operation, { revision: current.state?.revision || 0, device: 'cpu', ...payload });
  let message;
  return until(async () => {
    const value = await api(route);
    if (value.task?.message !== message) { message = value.task?.message;console.log(operation + ': ' + message); }
    if (['failed', 'cancelled'].includes(value.task?.status)) throw Error(message);
    return !value.task?.active && value.task?.status === 'complete' && value.state;
  }, 900000);
}
(async () => {
  assert.ok(process.env.SS_TEST_EXECUTABLE, 'Use the packaged executable selected by CI.');
  app = await electron.launch({ executablePath: process.env.SS_TEST_EXECUTABLE, env, timeout: 60000 });
  page = await app.firstWindow();const errors = [];page.on('pageerror', error => errors.push(error.message));
  await until(async () => {
    try { const i = instance(), s = await request(i.base + '/api/state', i.token);if (s.status === 'ready') { base = s.url;return true; } }
    catch { return false; }return false;
  }, 180000);
  base = new URL(base).origin;
  let state = await action('prepare');
  for (const key of ['speech', 'music', 'effects']) assert.ok(state.tracks[key].asset);
  const original = state.tracks.effects.asset;
  state = await action('cleanup', { track: 'effects', prompt: 'water bubbling', strength: .7, passes: 2, start: .2, end: .7 });
  const cleaned = state.tracks.effects.asset, removed = state.assets[cleaned].removed;
  assert.equal(state.assets[cleaned].parent, original);assert.ok(removed);
  assert.equal(state.assets[cleaned].cleanup.passes, 2);
  const tracks = structuredClone(state.tracks);tracks.music.regions = [{ start: .2, end: .7, db: -9 }];
  state = (await api(route, { revision: state.revision, tracks }, 'PUT')).state;
  state = await action('export', { video: true });
  assert.ok(state.export.files.some(file => file.endsWith('.mp4')), 'The real FFmpeg video export must succeed.');
  for (const file of state.export.files) {
    const response = await fetch(`${base}${route}/exports/${state.export.id}/${file}`);
    assert.ok(response.ok);assert.ok((await response.arrayBuffer()).byteLength > 0);
  }
  await page.goto(`${base}/lab?session=${session}`);await page.locator('#play').waitFor();
  assert.equal(await page.locator('.channel').count(), 4);await page.locator('#play').click();
  await page.waitForFunction(() => document.querySelector('#playback-label').textContent === 'Playing in sync');
  assert.equal(await page.locator('#video').evaluate(video => video.muted), true);
  await page.screenshot({ path: path.join(output, 'packaged-mixing-lab.png'), fullPage: true });
  // Numeric checks use the app's installed Python and its real output assets.
  const runtime = process.platform === 'darwin' ? path.join(home, 'runtimes', 'py311-macos-' + (process.arch === 'arm64' ? 'arm64' : 'x86_64') + '-cpu', 'bin/python3.11') : path.join(home, 'runtimes/py313-cpu/python.exe');
  const checked = spawnSync(runtime, ['-c', `import sys,json,pathlib,numpy as np,soundfile as sf
p=pathlib.Path(sys.argv[1]);s=json.loads((p/'state.json').read_text());a=s['assets'];c=s['tracks']['effects']['asset']
def read(k): return sf.read(p/'assets'/(k+'.wav'),dtype='float32',always_2d=True)
clean,rate=read(c);original,_=read(a[c]['parent']);removed,_=read(a[c]['removed'])
assert np.isfinite(clean).all() and clean.shape==original.shape
assert np.array_equal(clean[:round(.2*rate)],original[:round(.2*rate)])
assert np.array_equal(clean[round(.7*rate):],original[round(.7*rate):])
np.testing.assert_allclose(clean+removed,original,atol=3e-7)
e=p/'tasks'/s['export']['id']/'export';mix,mrate=sf.read(e/'mix.wav',always_2d=True)
assert mrate==rate and mix.shape==original.shape and np.isfinite(mix).all()
print(json.dumps({'frames':len(clean),'rate':rate,'channels':clean.shape[1],'outside_interval_unchanged':True,'cleaned_plus_removed':True}))`, path.join(home, 'data', session, 'lab')], { env, timeout: 30000, encoding: 'utf8', windowsHide: true });
  assert.equal(checked.status, 0, checked.stderr);const audio = JSON.parse(checked.stdout.trim());
  await page.locator('#close-session').click();await page.locator('#welcome').waitFor({ state: 'visible' });
  assert.equal((await api('/api/lab/sessions')).find(item => item.id === session).closed, true);
  await api(route + '/view', { closed: false }, 'PUT');
  assert.deepEqual(errors, []);
  fs.writeFileSync(path.join(output, 'creative-flows.json'), JSON.stringify({ platform: process.platform, arch: process.arch,
    prompt: 'water bubbling', passes: 2, actual_cpu_inference: true, lab_stems: true, video_playback: true,
    wav_zip_video_exports: true, persisted_close: true, audio, renderer_errors: errors,
    limitation: 'Synthetic one-second fixture verifies functionality, not separation quality.' }, null, 2));
  const closing = app.waitForEvent('close');await page.evaluate(() => { void window.soundshredderDesktop.quit(); });await closing;app = null;
  console.log('Packaged prompt cleanup, Mixing Lab playback/exports and retained source checks passed.');
})().catch(async error => {
  console.error(error);process.exitCode = 1;
  if (page) await page.screenshot({ path: path.join(output, 'creative-failure.png') }).catch(() => {});
}).finally(async () => {
  if (app) {
    try { const i = instance();await request(i.base + '/api/stop', i.token, {}); } catch {}
    // Failure teardown owns this disposable app. Do not wait on a native quit
    // dialog after the engine has already stopped; its owner pipe handles exit.
    await app.evaluate(({app}) => app.exit(1)).catch(() => {});
    await Promise.race([app.close().catch(() => {}), delay(5000)]);
  }
  if (process.exitCode) process.exit(process.exitCode);
});
