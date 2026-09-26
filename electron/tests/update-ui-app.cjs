// Private Electron fixture: real main/preload/window/controller, simulated engine
// and release transport. It cannot install anything or access a user profile.
const { app } = require('electron'), Module = require('node:module'), http = require('node:http');
const { EventEmitter } = require('node:events'), fs = require('node:fs'), path = require('node:path');
const root = path.resolve(__dirname, '../..');
if (!process.env.SOUNDSHREDDER_DESKTOP_HOME?.startsWith(path.join(root, 'artifacts') + path.sep)) throw Error('Use an isolated artifact profile.');
const { Updates } = require('../updates.cjs');
global.qa = { busy: false, installs: 0, stops: 0, recovered: 0 };
const fixture = http.createServer((req, res) => {
  if (req.url === '/desktop-updates.js') { res.setHeader('Content-Type', 'text/javascript');res.end(fs.readFileSync(path.join(root, 'static/desktop-updates.js'))); }
  else { res.setHeader('Content-Type', 'text/html');res.end('<!doctype html><title>Private update QA workspace</title><button id="updates" onclick="window.soundshredderDesktop.openUpdates()">Desktop updates</button><p id="update-info"></p><script src="/desktop-updates.js"></script>'); }
});
class FakeUpdater extends EventEmitter {
  async checkForUpdates() {
    if (qa.failCheck) throw Error('Offline');
    return { isUpdateAvailable: true, updateInfo: { version: '1.3.0', releaseNotes: '<img src=x onerror="window.injected=true">Useful changes.',
      files: [{ url: `SoundShredder-1.3.0-${process.arch}${process.platform === 'darwin' ? '.zip' : '.exe'}`, size: 125000000, sha512: 'fixture' }] } };
  }
  downloadUpdate(token) { return token.createPromise(resolve => { qa.complete = resolve; }); }
  quitAndInstall() { qa.installs++; }
}
const updater = qa.updater = new FakeUpdater();
const originalLoad = Module._load;
Module._load = function(id, ...args) {
  if (id === './updates.cjs') return { Updates: class extends Updates {
    constructor(options) { super({ ...options, version: '1.2.2', updater, enabled: true, checkTimeout: 100, stallTimeout: 10000 });qa.service = this; }
  } };
  if (id === './backend.cjs') return { Backend: class extends EventEmitter {
    constructor(root, home) { super();this.root = root;this.home = home; }
    async start() { this.base = `http://127.0.0.1:${fixture.address().port}`;this.child = { exitCode: null };qa.recovered++; }
    setupURL() { return this.base; }
    async api(route) { if (route === '/api/stop') { qa.stops++;if (qa.busy) throw Object.assign(Error('Audio job running'), { statusCode: 409 }); }return { status: 'ready', url: this.base }; }
    async detach() { this.child.exitCode = 0; }
  } };
  return originalLoad.call(this, id, ...args);
};
fixture.listen(0, '127.0.0.1', () => require('../main.cjs'));
app.on('will-quit', () => fixture.close());
