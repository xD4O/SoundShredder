'use strict';
const { EventEmitter } = require('node:events');
const { CancellationToken } = require('builder-util-runtime');
const stable = version => typeof version === 'string' && /^\d+\.\d+\.\d+$/.test(version);
function plainNotes(value) {
  // GitHub's Atom feed supplies HTML. Convert its common formatting to text;
  // the renderer still uses textContent exclusively, including decoded entities.
  const entities = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };
  return String(value).slice(0, 64000).replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, '')
    .replace(/<li\b[^>]*>/gi, '\n• ').replace(/<br\s*\/?\s*>|<\/(?:p|div|h[1-6]|li|ul|ol)>/gi, '\n')
    .replace(/<[^>]*>/g, '').replace(/&(amp|lt|gt|quot|apos|nbsp);/g, (_, name) => entities[name])
    .replace(/&#(x[\da-f]+|\d+);/gi, (match, number) => {
      const code = number.toLowerCase().startsWith('x') ? parseInt(number.slice(1), 16) : Number(number);
      return code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : match;
    }).replace(/\n{3,}/g, '\n\n').trim().slice(0, 16000);
}
function releaseDetails(info, platform, arch) {
  if (!stable(info?.version)) throw Error('A stable release is required.');
  const extension = platform === 'darwin' ? '.zip' : '.exe';
  const files = (info.files || []).filter(file => file.url?.endsWith(extension));
  const fileArch = file => /(?:^|[-_.])(arm64|x64|ia32|universal)(?:[-_.]|$)/.exec(file.url)?.[1];
  const file = files.find(file => fileArch(file) === arch) || files.find(file => fileArch(file) === 'universal') ||
    (files.length === 1 && !fileArch(files[0]) ? files[0] : null);
  if (!file || !file.sha512) throw Error('This release does not have a matching download.');
  const notes = Array.isArray(info.releaseNotes) ? info.releaseNotes.map(item => item.note || '').join('\n\n') : info.releaseNotes;
  return { version: info.version, size: Number.isFinite(file.size) ? file.size : null,
    notes: plainNotes(notes || 'See the release notes on GitHub.'),
    releaseURL: `https://github.com/xD4O/SoundShredder/releases/tag/v${info.version}` };
}
function deadline(promise, milliseconds, message) {
  let timer;
  return Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(Error(message)), milliseconds); })])
    .finally(() => clearTimeout(timer));
}

class Updates extends EventEmitter {
  constructor({ updater, version, enabled, platform = process.platform, arch = process.arch, prepareInstall,
    recoverInstall = async () => {}, checkTimeout = 20000, stallTimeout = 90000 }) {
    super();
    Object.assign(this, { updater, platform, arch, prepareInstall, recoverInstall, checkTimeout, stallTimeout });
    this.enabled = enabled && ['win32', 'darwin'].includes(platform);
    this.state = { status: this.enabled ? 'idle' : 'unsupported', currentVersion: version,
      message: this.enabled ? 'Updates come from the official SoundShredder releases.' : 'Install a desktop release to use in-app updates. Source builds update manually.' };
    this.serial = 0;
    updater.autoDownload = false;
    updater.autoInstallOnAppQuit = false; // Later and ordinary Quit must never install.
    updater.autoRunAppAfterInstall = true;
    updater.allowPrerelease = false;
    updater.allowDowngrade = false;
    updater.disableWebInstaller = true;
    updater.on('download-progress', progress => {
      if (this.state.status !== 'downloading') return;
      if (progress.transferred > (this.state.transferred || 0)) this.lastActivity = Date.now();
      this.set({ percent: Math.max(0, Math.min(100, progress.percent || 0)),
        transferred: progress.transferred, total: progress.total, bytesPerSecond: progress.bytesPerSecond });
    });
    // Check/download promises report their own errors. Native installation
    // errors can arrive after quitAndInstall has returned.
    updater.on('error', () => {
      if (this.state.status === 'installing') void this.installFailed();
    });
  }
  snapshot() { return { ...this.state }; }
  set(value) { this.state = { ...this.state, ...value }; this.emit('change', this.snapshot()); return this.snapshot(); }
  async check() {
    if (!this.enabled || ['checking', 'downloading', 'cancelling', 'downloaded', 'installing'].includes(this.state.status)) return this.snapshot();
    const serial = ++this.serial;
    this.set({ status: 'checking', message: 'Checking GitHub for a stable release…', version: null, notes: '', size: null, percent: 0 });
    try {
      const result = await deadline(this.updater.checkForUpdates(), this.checkTimeout, 'Update check timed out.');
      if (serial !== this.serial) return this.snapshot();
      if (!result) throw Error('Updates unavailable.');
      if (!result.isUpdateAvailable) return this.set({ status: 'current', message: 'You have the latest compatible stable release.', checkedAt: Date.now() });
      return this.set({ ...releaseDetails(result.updateInfo, this.platform, this.arch), status: 'available', checkedAt: Date.now(),
        message: 'An update is available. Download it when you are ready.' });
    } catch {
      if (serial === this.serial) this.set({ status: 'error', message: 'Could not check for updates. Check your connection and retry, or open GitHub releases.' });
      return this.snapshot();
    }
  }
  async download() {
    if (!this.enabled || this.state.status !== 'available') return this.snapshot();
    const serial = ++this.serial;
    this.token = new CancellationToken();this.lastActivity = Date.now();
    this.set({ status: 'downloading', message: 'Downloading in the background. You can keep working.', percent: 0, transferred: 0 });
    let stalled = false;
    const watchdog = setInterval(() => {
      if (Date.now() - this.lastActivity > this.stallTimeout) { stalled = true; this.token.cancel(); }
    }, Math.min(1000, this.stallTimeout));
    try {
      await this.updater.downloadUpdate(this.token);
      if (serial !== this.serial) return this.snapshot();
      if (this.token.cancelled) throw Error('Cancelled');
      return this.set({ status: 'downloaded', percent: 100, message: 'Ready to install. Restart when your audio work is finished.' });
    } catch {
      if (serial !== this.serial) return this.snapshot();
      return this.set({ status: this.token.cancelled && !stalled ? 'available' : 'error',
        message: this.token.cancelled && !stalled ? 'Download cancelled. Your current app is unchanged.' :
          'Download or verification failed. Check your connection and free disk space, then check again. Your current app is unchanged.' });
    } finally { clearInterval(watchdog); }
  }
  cancel() {
    if (this.state.status === 'downloading') {
      this.set({ status: 'cancelling', message: 'Cancelling download…' });this.token.cancel();
    }
    return this.snapshot();
  }
  async install() {
    if (this.state.status !== 'downloaded') return this.snapshot();
    this.set({ status: 'installing', message: 'Checking your workspace and preparing to restart…' });
    try {
      await this.prepareInstall(); // Must reject if busy or unable to confirm idle.
    } catch {
      return this.set({ status: 'downloaded', message: 'Finish or cancel processing, uploads, saves, downloads and setup before restarting. If the engine is unavailable, reopen the workspace and retry.' });
    }
    try { this.updater.quitAndInstall(true, true); }
    catch { await this.installFailed(); }
    return this.snapshot();
  }
  async installFailed() {
    if (this.state.status !== 'installing') return;
    this.set({ status: 'error', message: 'The update could not start. Reopen your workspace or install the release manually. Saved sessions are kept.' });
    await this.recoverInstall().catch(() => {});
  }
}
module.exports = { Updates, releaseDetails, deadline };
