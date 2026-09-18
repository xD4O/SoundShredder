// Fault injection for the real setup page: a slow diagnostics request and a
// stalled state poll must not prevent Cancel, repainting, or reconnection.
const { _electron: electron } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const root = path.resolve(__dirname, '../..');
const output = path.join(root, 'artifacts/electron/verification');
fs.mkdirSync(output, { recursive: true });
const assets = { '/': 'desktop/setup.html', '/font.ttf': 'static/fonts/SpaceGrotesk-Variable.ttf',
  '/higgsfield.svg': 'static/higgsfield-mark.svg', '/icon.svg': 'static/icon.svg' };
const mime = { '.html': 'text/html', '.ttf': 'font/ttf', '.svg': 'image/svg+xml' };
let application, holdState = false, held = 0, cancelled = false, diagnostics = 0;
const server = http.createServer((req, res) => {
  if (assets[req.url]) {
    res.setHeader('Content-Type', mime[path.extname(assets[req.url])]);
    return res.end(fs.readFileSync(path.join(root, assets[req.url])));
  }
  assert.equal(req.headers['x-setup-token'], 'qa-only');
  if (req.url === '/api/diagnostics') { diagnostics++; return; }
  if (req.url === '/api/state' && holdState) { held++; return; }
  res.setHeader('Content-Type', 'application/json');
  if (req.url === '/api/cancel-setup') { cancelled = true; return res.end('{"ok":true}'); }
  const s = { status: cancelled ? 'idle' : 'installing', message: cancelled ? 'Setup canceled. Your sessions are kept.' : 'Downloading the CPU audio engine…',
    platform: 'win32', device: 'cpu', machine: 'x64', nvidia: false, home: 'C:\\Users\\Creator\\AppData\\Local\\SoundShredder', free_gib: 30,
    required_gib: { cpu: 4, cuda: 14 }, progress: cancelled ? 0 : 20, can_cancel: !cancelled,
    activity: 'Downloading torch…', elapsed_seconds: 65, quiet_seconds: 0,
    download: { received: 125829120, total: 209715200, bytes_per_second: 2097152 } };
  res.end(JSON.stringify(s));
});
async function checkUntil(fn, timeout = 12000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) { if (await fn()) return; await new Promise(r => setTimeout(r, 100)); }
  throw Error('Setup UI did not recover within the deadline');
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${server.address().port}/#qa-only`;
  const harness = path.join(root, 'artifacts/electron/setup-ui-harness.cjs');
  fs.writeFileSync(harness, `const {app,BrowserWindow}=require('electron');app.whenReady().then(()=>{const w=new BrowserWindow({width:1280,height:1050,webPreferences:{sandbox:true,contextIsolation:true,nodeIntegration:false}});w.loadURL(${JSON.stringify(url)});});app.on('window-all-closed',()=>app.quit());`);
  const env = { ...process.env }; delete env.ELECTRON_RUN_AS_NODE;
  application = await electron.launch({ executablePath: require('electron'), args: [harness, '--user-data-dir=' + path.join(root, 'artifacts/electron/setup-ui-profile')], env });
  const page = await application.firstWindow();
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await page.locator('#cancel').waitFor({ state: 'visible' });
  await page.evaluate(() => document.fonts.ready);
  assert.match(await page.locator('#download-label').textContent(), /120.0 MiB \/ 200.0 MiB/);
  await page.screenshot({ path: path.join(output, 'setup-ui-desktop.png'), fullPage: true });
  await page.locator('#diagnostics').click();
  await checkUntil(() => diagnostics > 0);
  const before = await page.locator('#timing').textContent();
  await checkUntil(async () => (await page.locator('#timing').textContent()) !== before);
  assert.ok(await page.locator('#cancel').isEnabled(), 'Slow diagnostics must not block Cancel');
  holdState = true;
  await checkUntil(() => held > 0);
  await page.locator('#connection').waitFor({ state: 'visible', timeout: 10000 });
  assert.match(await page.locator('#connection').textContent(), /Reconnecting/);
  await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(390, 950));
  await page.screenshot({ path: path.join(output, 'setup-ui-mobile.png'), fullPage: true });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'No horizontal overflow');
  const started = Date.now();
  await page.locator('#cancel').click();
  await checkUntil(() => cancelled, 2000);
  assert.ok(Date.now() - started < 2000, 'Cancel must still dispatch while polling is stalled');
  holdState = false;
  await checkUntil(async () => (await page.locator('#message').textContent()).includes('Setup canceled'), 15000);
  assert.ok(await page.locator('#connection').isHidden());
  assert.ok(await page.locator('#start').isVisible());
  assert.deepEqual(errors, []);
  const evidence = { download_display: true, slow_diagnostics_keeps_timer_and_cancel: true,
    stalled_poll_times_out: true, cancel_while_disconnected: true, reconnects: true, mobile_no_overflow: true, renderer_errors: errors };
  fs.writeFileSync(path.join(output, 'setup-ui.json'), JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify(evidence));
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => {
  if (application) await application.close();
  server.closeAllConnections(); server.close();
});
