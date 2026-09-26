const { test } = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const { Updates, releaseDetails } = require('../updates.cjs');
const info = { version: '1.3.0', releaseNotes: '<script>untrusted notes</script>', files: [
  { url: 'SoundShredder-1.3.0-Windows-x64-Setup.exe', sha512: 'hash', size: 120000000 },
  { url: 'SoundShredder-1.3.0-macOS-arm64.zip', sha512: 'hash', size: 110000000 },
  { url: 'SoundShredder-1.3.0-macOS-x64.zip', sha512: 'hash', size: 115000000 },
] };
class FakeUpdater extends EventEmitter {
  async checkForUpdates() { this.checks = (this.checks || 0) + 1;return { isUpdateAvailable: true, updateInfo: info }; }
  async downloadUpdate(token) { this.token = token; }
  quitAndInstall() { this.installs = (this.installs || 0) + 1; }
}
function fixture(extra = {}) {
  const updater = new FakeUpdater();
  const service = new Updates({ updater, enabled: true, version: '1.2.2', platform: 'win32',
    prepareInstall: async () => {}, ...extra });
  return { service, updater };
}
test('stable updates are checked without downloading or installing on normal quit', async () => {
  const { service, updater } = fixture();await service.check();
  assert.equal(service.state.status, 'available');assert.equal(service.state.size, 120000000);
  assert.equal(updater.autoDownload, false);assert.equal(updater.autoInstallOnAppQuit, false);
  assert.equal(updater.allowDowngrade, false);assert.equal(updater.allowPrerelease, false);
  assert.equal(updater.disableWebInstaller, true);assert.equal(updater.token, undefined);
  assert.equal(releaseDetails(info, 'darwin', 'arm64').size, 110000000);
  assert.throws(() => releaseDetails({ ...info, version: '1.3.0-beta.1' }, 'win32', 'x64'));
  assert.throws(() => releaseDetails({ ...info, files: [info.files[1]] }, 'darwin', 'x64'), /matching download/);
  assert.throws(() => releaseDetails({ ...info, files: [{ ...info.files[0], sha512: null }] }, 'win32', 'x64'));
});
test('source builds never contact the update service', async () => {
  const { service, updater } = fixture({ enabled: false });
  await service.check();await service.download();await service.install();
  assert.equal(service.state.status, 'unsupported');assert.equal(updater.checks, undefined);
});

test('GitHub HTML notes become readable text without executable markup', () => {
  const notes = releaseDetails({ ...info, releaseNotes: '<h2>Changes &amp; fixes</h2><ul><li>Saved mixes</li></ul><script>bad()</script><p>&lt;code&gt;</p>' }, 'win32', 'x64').notes;
  assert.equal(notes, 'Changes & fixes\n\n• Saved mixes\n\n<code>');
});
test('check deadlines recover the UI and ignore late responses', async () => {
  const { service, updater } = fixture({ checkTimeout: 15 });let finish;
  updater.checkForUpdates = () => new Promise(resolve => { finish = resolve; });
  await service.check();assert.equal(service.state.status, 'error');
  finish({ isUpdateAvailable: true, updateInfo: info });await new Promise(resolve => setImmediate(resolve));
  assert.equal(service.state.status, 'error');
  updater.checkForUpdates = async () => ({ isUpdateAvailable: false, updateInfo: info });
  await service.check();assert.equal(service.state.status, 'current');
});
test('cancelled downloads settle before another download can start', async () => {
  const { service, updater } = fixture();await service.check();let downloads = 0;
  updater.downloadUpdate = token => { downloads++;return token.createPromise(() => {}); };
  const work = service.download();assert.equal(service.state.status, 'downloading');
  service.cancel();assert.equal(service.state.status, 'cancelling');
  await service.download();await work;assert.equal(downloads, 1);assert.equal(service.state.status, 'available');
  assert.equal(updater.installs, undefined);
});
test('stalled downloads cancel and keep the installed app unchanged', async () => {
  const { service, updater } = fixture({ stallTimeout: 10 });await service.check();
  updater.downloadUpdate = token => token.createPromise(() => {});
  await service.download();assert.equal(service.state.status, 'error');assert.equal(updater.installs, undefined);
});
test('a rejected checksum or signature cannot become an installable update', async () => {
  const { service, updater } = fixture();await service.check();
  updater.downloadUpdate = async () => { throw Error('Checksum mismatch'); };
  await service.download();await service.install();
  assert.equal(service.state.status, 'error');assert.equal(updater.installs, undefined);
});
test('restart waits for successful engine shutdown and rejects busy or unreachable engines', async () => {
  let busy = true, stopped = false;
  const { service, updater } = fixture({ prepareInstall: async () => { if (busy) throw Error('Audio job running');stopped = true; } });
  updater.quitAndInstall = () => { assert.equal(stopped, true);updater.installs = 1; };
  await service.check();await service.download();await service.install();
  assert.equal(service.state.status, 'downloaded');assert.equal(updater.installs, undefined);
  busy = false;await service.install();assert.equal(updater.installs, 1);
});
test('native install errors reopen the current app instead of leaving it stopped', async () => {
  let recovered = 0;const { service, updater } = fixture({ recoverInstall: async () => { recovered++; } });
  updater.quitAndInstall = () => updater.emit('error', Error('Native verification failed'));
  await service.check();await service.download();await service.install();
  assert.equal(service.state.status, 'error');assert.equal(recovered, 1);
});
test('parallel check/restart clicks do not duplicate operations', async () => {
  let finish;const { service, updater } = fixture({ prepareInstall: () => new Promise(resolve => { finish = resolve; }) });
  await Promise.all([service.check(), service.check()]);assert.equal(updater.checks, 1);
  await service.download();const installing = service.install();await service.install();
  finish();await installing;assert.equal(updater.installs, 1);
});
