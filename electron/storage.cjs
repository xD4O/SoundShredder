'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');
const { randomUUID } = require('node:crypto');

const preferenceName = 'desktop-storage.json';
const normalize = value => process.platform === 'win32' ? path.resolve(value).toLowerCase() : path.resolve(value);
function contains(parent, child) {
  const relative = path.relative(normalize(parent), normalize(child));
  return relative === '' || (!relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative));
}
async function readSelection(controlHome) {
  let raw;
  try { raw = await fs.readFile(path.join(controlHome, preferenceName), 'utf8'); }
  catch (error) { if (error.code === 'ENOENT') return { home: controlHome, managedStorage: false }; throw error; }
  let saved;
  try { saved = JSON.parse(raw); } catch { /* Explain how to recover instead of silently using another drive. */ }
  if (saved?.version !== 1 || typeof saved.home !== 'string' || !path.isAbsolute(saved.home) || saved.home.includes('\0')) {
    throw Error('The saved storage location could not be read. Choose a storage folder to recover; existing files are kept.');
  }
  return { home: path.resolve(saved.home), managedStorage: true };
}
async function saveSelection(controlHome, home) {
  await fs.mkdir(controlHome, { recursive: true });
  const temporary = path.join(controlHome, `.${preferenceName}.${randomUUID()}.tmp`);
  try {
    await fs.writeFile(temporary, JSON.stringify({ version: 1, home }, null, 2), { flag: 'wx' });
    for (let attempt = 0; ; attempt++) {
      try { await fs.rename(temporary, path.join(controlHome, preferenceName)); break; }
      catch (error) {
        if (!['EACCES', 'EPERM', 'EBUSY'].includes(error.code) || attempt >= 5) throw error;
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    }
  } finally { await fs.unlink(temporary).catch(error => { if (error.code !== 'ENOENT') throw error; }); }
}
async function existingDirectory(folder) {
  try {
    if (!(await fs.stat(folder)).isDirectory()) throw Error('Not a directory');
    return await fs.realpath(folder);
  } catch {
    throw Error('The storage folder is unavailable. Reconnect its drive, or choose another storage folder. Existing files have not been moved.');
  }
}
async function prepareLocation(selected, { currentHome, protectedPaths = [], timeout = 8000 } = {}) {
  const controller = new AbortController();
  let timer;
  const work = (async () => {
    const check = () => controller.signal.throwIfAborted();
    if (typeof selected !== 'string' || !path.isAbsolute(selected) || selected.includes('\0') ||
        (process.platform === 'win32' && selected.startsWith('\\\\'))) {
      throw Error('Choose a folder on a local or attached drive.');
    }
    const parent = await existingDirectory(selected); check();
    let home = path.basename(parent).toLowerCase() === 'soundshredder' || (currentHome && normalize(parent) === normalize(currentHome))
      ? parent : path.join(parent, 'SoundShredder');
    const verify = async candidate => {
      for (const entry of protectedPaths) {
        const protectedPath = await fs.realpath(entry).catch(() => path.resolve(entry)); check();
        if (contains(protectedPath, candidate) || contains(candidate, protectedPath)) {
          throw Error('Choose a data folder separate from the installed application folder. This keeps your audio safe when uninstalling.');
        }
      }
      if (currentHome) {
        const current = await fs.realpath(currentHome).catch(() => path.resolve(currentHome)); check();
        if (normalize(current) !== normalize(candidate) && (contains(current, candidate) || contains(candidate, current))) {
          throw Error('Choose a separate location, outside your current SoundShredder storage folder.');
        }
      }
    };
    await verify(home); check();
    await fs.mkdir(home, { recursive: true }); check();
    home = await fs.realpath(home); check();
    await verify(home); check();
    let probe;
    try {
      probe = await fs.mkdtemp(path.join(home, '.write-check-')); check();
      await fs.writeFile(path.join(probe, 'test'), 'SoundShredder', { signal: controller.signal }); check();
    } catch (error) {
      if (controller.signal.aborted) throw controller.signal.reason;
      throw Error('SoundShredder cannot write to that folder. Choose a writable location on your drive.', { cause: error });
    } finally {
      if (probe) {
        await fs.unlink(path.join(probe, 'test')).catch(() => {});
        await fs.rmdir(probe).catch(() => {});
      }
    }
    const space = await fs.statfs(home); check();
    return { home, freeGiB: Number(space.bavail) * Number(space.bsize) / 1024 ** 3 };
  })();
  try {
    return await Promise.race([work, new Promise((_, reject) => {
      timer = setTimeout(() => {
        const error = Error('That drive is taking too long to respond. Check it is connected, then try again.');
        controller.abort(error); reject(error);
      }, timeout);
    })]);
  } finally { clearTimeout(timer); }
}
module.exports = { readSelection, saveSelection, existingDirectory, prepareLocation, contains };
