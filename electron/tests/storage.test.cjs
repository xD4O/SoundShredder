const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { readSelection, saveSelection, existingDirectory, prepareLocation } = require('../storage.cjs');
const { storageEnvironment, Backend } = require('../backend.cjs');

async function fixture(t) {
  const temporaryRoot = await fs.realpath(os.tmpdir());
  const root = await fs.realpath(await fs.mkdtemp(path.join(temporaryRoot, 'soundshredder-storage-')));
  t.after(async () => {
    assert.equal(path.dirname(await fs.realpath(root)), temporaryRoot);
    assert.ok(path.basename(root).startsWith('soundshredder-storage-'));
    await fs.rm(root, { recursive: true, force: true });
  });
  const control = path.join(root, 'Control');
  const drive = path.join(root, 'Another drive with spaces');
  await fs.mkdir(drive);
  return { root, control, drive };
}
test('select, persist, reopen and replace locations without deleting original audio', async t => {
  const { control, drive } = await fixture(t);
  assert.deepEqual(await readSelection(control), { home: control, managedStorage: false });
  await fs.mkdir(path.join(control, 'data'), { recursive: true });
  await fs.writeFile(path.join(control, 'data', 'original.wav'), 'keep');
  const selected = await prepareLocation(drive, { currentHome: control });
  assert.equal(selected.home, await fs.realpath(path.join(drive, 'SoundShredder')));
  assert.ok(selected.freeGiB > 0);
  assert.deepEqual(await fs.readdir(selected.home), []);
  await saveSelection(control, selected.home);
  assert.deepEqual(await readSelection(control), { home: selected.home, managedStorage: true });
  assert.equal((await prepareLocation(selected.home, { currentHome: control })).home, selected.home);
  await saveSelection(control, control);
  assert.equal((await readSelection(control)).home, control);
  assert.equal(await fs.readFile(path.join(control, 'data', 'original.wav'), 'utf8'), 'keep');
});
test('unavailable or malformed selections never silently fall back or create a replacement', async t => {
  const { control, drive } = await fixture(t);
  const missing = path.join(drive, 'Offline', 'SoundShredder');
  await saveSelection(control, missing);
  assert.equal((await readSelection(control)).home, missing);
  await assert.rejects(existingDirectory(missing), /Reconnect/);
  await assert.rejects(fs.stat(missing), { code: 'ENOENT' });
  await fs.writeFile(path.join(control, 'desktop-storage.json'), '{broken');
  await assert.rejects(readSelection(control), /Choose a storage folder/);
});
test('the picker refuses app folders, nested profiles and relative paths', async t => {
  const { root, control, drive } = await fixture(t);
  await fs.mkdir(path.join(control, 'runtimes'), { recursive: true });
  await assert.rejects(prepareLocation(path.join(control, 'runtimes'), { currentHome: control }), /outside your current/);
  await assert.rejects(prepareLocation(drive, { protectedPaths: [root] }), /separate from the installed/);
  await assert.rejects(prepareLocation('relative'), /local or attached drive/);
});
test('a redirected profile cannot place user data inside the application bundle', async t => {
  const { root, drive } = await fixture(t);
  const app = path.join(root, 'Installed App'); await fs.mkdir(app);
  await fs.symlink(app, path.join(drive, 'SoundShredder'), process.platform === 'win32' ? 'junction' : 'dir');
  await assert.rejects(prepareLocation(drive, { protectedPaths: [app] }), /separate from the installed/);
  assert.deepEqual(await fs.readdir(app), []);
});
test('all large downloads and installer temporary files use the chosen drive', async t => {
  const { drive } = await fixture(t);
  const selected = path.join(drive, 'SoundShredder');
  const env = storageEnvironment(selected);
  for (const value of Object.values(env)) assert.ok(value.startsWith(selected + path.sep));
  assert.equal(env.BANDIT_INFER_WEIGHTS, path.join(selected, 'models/bandit-infer'));
  assert.equal(env.SOUNDSHREDDER_MODEL_HOME, path.join(selected, 'models'));
  assert.equal(env.TEMP, path.join(selected, 'temp'));
  assert.equal(env.HOME, undefined);
  assert.equal(env.USERPROFILE, undefined);
});
test('backend startup refuses an offline selection before creating a replacement profile', async t => {
  const { root, drive } = await fixture(t);
  const missing = path.join(drive, 'Offline', 'SoundShredder');
  const backend = new Backend(root, missing, true);
  await assert.rejects(backend.start(), /Reconnect/);
  assert.equal(backend.child, null);
  await assert.rejects(fs.stat(missing), { code: 'ENOENT' });
});
