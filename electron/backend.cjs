'use strict';
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { spawn } = require('node:child_process');
const { EventEmitter } = require('node:events');
const { loopback } = require('./security.cjs');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

function request(url, token, payload, timeout = 5000) {
  if (!loopback(url)) return Promise.reject(new Error('Invalid local engine address.'));
  return new Promise((resolve, reject) => {
    const data = payload === undefined ? undefined : JSON.stringify(payload);
    const req = http.request(url, { method: data ? 'POST' : 'GET', headers: {
      'X-Setup-Token': token, ...(data ? {'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data)} : {})
    } }, res => {
      let body = '';
      res.on('data', chunk => { body += chunk; if (body.length > 65536) req.destroy(new Error('Invalid engine response.')); });
      res.on('end', () => {
        try {
          const value = JSON.parse(body);
          if (res.statusCode !== 200) {
            const error = new Error(value.error || 'Engine request failed.');
            error.statusCode = res.statusCode;
            throw error;
          }
          resolve(value);
        } catch (error) { reject(error); }
      });
      res.on('error', reject);
    });
    req.setTimeout(timeout, () => req.destroy(new Error('The audio engine is not responding.')));
    req.on('error', reject);
    req.end(data);
  });
}

class Backend extends EventEmitter {
  constructor(root, home) {
    super(); this.root = root; this.home = home; this.child = null; this.base = null; this.token = null;
  }
  async start() {
    if (this.child && this.child.exitCode === null && !this.child.signalCode) throw new Error('The previous engine is still closing. Try again in a moment.');
    this.base = this.token = null;
    fs.mkdirSync(this.home, { recursive: true });
    const python = path.join(this.root, 'python', process.platform === 'darwin' ? 'bin/python3.11' : 'python.exe');
    if (!fs.existsSync(python)) throw new Error('The bundled Python runtime is missing. Reinstall SoundShredder; saved sessions will be retained.');
    const script = path.join(this.root, 'desktop/bootstrap.py');
    const code = `import sys,runpy; sys.path.insert(0,${JSON.stringify(this.root)}); sys.argv[0]=${JSON.stringify(script)}; runpy.run_path(sys.argv[0],run_name='__main__')`;
    const log = fs.openSync(path.join(this.home, 'electron-engine.log'), 'a');
    const env = { ...process.env, PYTHONUTF8: '1', PYTHONNOUSERSITE: '1', SOUNDSHREDDER_DESKTOP_HOME: this.home };
    delete env.PYTHONHOME; delete env.PYTHONPATH;
    let child;
    try {
      child = this.child = spawn(python, [...(process.platform === 'darwin' ? ['-I'] : []), '-c', code,
        '--home', this.home, '--hosted', '--exclusive', '--no-browser'],
      { cwd: this.root, env, windowsHide: true, stdio: ['pipe', log, log] });
    } finally { fs.closeSync(log); }
    let spawnError;
    child.on('error', error => { spawnError = error; });
    child.stdin.on('error', () => {});
    child.on('exit', (code, signal) => this.emit('exit', { code, signal }));
    const deadline = Date.now() + 25000;
    while (Date.now() < deadline) {
      if (spawnError || child.exitCode !== null || child.signalCode) {
        throw new Error('SoundShredder could not start. Close any older standalone first, then retry. Details: ' + path.join(this.home, 'electron-engine.log'));
      }
      try {
        const saved = JSON.parse(fs.readFileSync(path.join(this.home, 'desktop.json'), 'utf8'));
        const u = loopback(saved.url);
        if (saved.pid === child.pid && u && u.pathname === '/' && !u.search && u.hash.length > 1) {
          const state = await request(u.origin + '/api/state', u.hash.slice(1));
          if (state.pid === child.pid && path.resolve(state.home) === path.resolve(this.home)) {
            this.base = u.origin; this.token = u.hash.slice(1); return state;
          }
        }
      } catch { /* The manager may still be writing startup metadata. */ }
      await delay(150);
    }
    await this.detach();
    throw new Error('The audio engine took too long to open. Check Setup and diagnostics, then retry.');
  }
  setupURL() { return this.base + '/#' + this.token; }
  api(route, payload) {
    if (!this.base) return Promise.reject(new Error('The audio engine is not ready.'));
    return request(this.base + route, this.token, payload);
  }
  async detach() {
    const child = this.child;
    if (!child || child.exitCode !== null || child.signalCode) return;
    child.stdin.end(); // Owner-pipe EOF cleans up Python and its audio workers.
    for (let i = 0; i < 150 && child.exitCode === null && !child.signalCode; i++) await delay(100);
    if (child.exitCode === null && !child.signalCode) child.kill();
  }
}
module.exports = { Backend, request };
