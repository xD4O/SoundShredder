const { test } = require('node:test');
const assert = require('node:assert/strict'), fs = require('node:fs'), os = require('node:os'), path = require('node:path'), crypto = require('node:crypto');
const yaml = require('js-yaml'), { merge } = require('../build/merge-updates.cjs');
test('merge verifies payload bytes and retains both Mac architectures', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ss-update-metadata-'));
  const input = path.join(root, 'input'), output = path.join(root, 'output');
  for (const arch of ['arm64', 'x64']) {
    const folder = path.join(input, arch);fs.mkdirSync(folder, { recursive: true });
    const url = `SoundShredder-1.3.0-${arch}.zip`, body = Buffer.from(arch);
    fs.writeFileSync(path.join(folder, url), body);
    fs.writeFileSync(path.join(folder, 'latest-mac.yml'), yaml.dump({ version: '1.3.0', files: [
      { url, size: body.length, sha512: crypto.createHash('sha512').update(body).digest('base64') },
    ] }));
  }
  assert.deepEqual(await merge(input, output), ['latest-mac.yml']);
  assert.equal(yaml.load(fs.readFileSync(path.join(output, 'latest-mac.yml'), 'utf8')).files.length, 2);
  fs.appendFileSync(path.join(input, 'x64/SoundShredder-1.3.0-x64.zip'), 'changed');
  await assert.rejects(merge(input, output), /bytes do not match/);
});
