'use strict';
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const yaml = require('js-yaml');
function walk(root) { return fs.readdirSync(root, { withFileTypes: true }).flatMap(item => item.isDirectory() ? walk(path.join(root, item.name)) : [path.join(root, item.name)]); }
async function digest(file) {
  const hash = crypto.createHash('sha512');for await (const chunk of fs.createReadStream(file)) hash.update(chunk);return hash.digest('base64');
}
async function merge(input, output) {
  const paths = walk(input), manifests = paths.filter(file => /^latest(?:-mac)?\.yml$/.test(path.basename(file))), groups = new Map();
  if (!manifests.length) throw Error('No stable update manifests found.');
  const versions = new Set();
  for (const file of manifests) {
    const info = yaml.load(fs.readFileSync(file, 'utf8'));
    if (!/^\d+\.\d+\.\d+$/.test(info?.version) || !Array.isArray(info.files) || !info.files.length) throw Error('Invalid stable update manifest.');
    versions.add(info.version);const name = path.basename(file);
    const group = groups.get(name) || { ...info, files: [] };
    for (const asset of info.files) {
      if (typeof asset.url !== 'string' || path.basename(asset.url) !== asset.url || /[\\/?#]/.test(asset.url)) throw Error('Update files must be local release asset names.');
      const candidates = paths.filter(candidate => path.basename(candidate) === asset.url);
      if (candidates.length !== 1) throw Error(`Missing or duplicated release asset: ${asset.url}`);
      const actual = await digest(candidates[0]);
      if (actual !== asset.sha512 || fs.statSync(candidates[0]).size !== asset.size) throw Error(`Release bytes do not match metadata: ${asset.url}`);
      if (group.files.some(item => item.url === asset.url)) throw Error(`Duplicate update entry: ${asset.url}`);
      group.files.push(asset);
    }
    groups.set(name, group);
  }
  if (versions.size !== 1) throw Error('All platform manifests must describe the same version.');
  fs.mkdirSync(output, { recursive: true });
  for (const [name, group] of groups) {
    // Modern clients select the matching architecture from files. Preserve
    // consistent legacy fields using a ZIP for Mac and the EXE for Windows.
    const primary = group.files.find(file => file.url.endsWith(name === 'latest-mac.yml' ? '.zip' : '.exe'));
    if (!primary) throw Error(`Missing update payload for ${name}`);
    group.path = primary.url;group.sha512 = primary.sha512;
    fs.writeFileSync(path.join(output, name), yaml.dump(group));
  }
  return [...groups.keys()];
}
if (require.main === module) {
  if (process.argv.length !== 4) throw Error('Use merge-updates.cjs INPUT_DIRECTORY OUTPUT_DIRECTORY');
  merge(path.resolve(process.argv[2]), path.resolve(process.argv[3])).then(names => console.log(`Verified update metadata: ${names.join(', ')}`))
    .catch(error => { console.error(error.message);process.exitCode = 1; });
}
module.exports = { merge };
