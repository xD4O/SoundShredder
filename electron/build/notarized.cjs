'use strict';
const path = require('node:path');

function releaseConfig(env) {
  const required = ['CSC_LINK', 'CSC_KEY_PASSWORD', 'CSC_NAME', 'APPLE_ID', 'APPLE_APP_SPECIFIC_PASSWORD', 'APPLE_TEAM_ID'];
  const missing = required.filter(name => !env[name]?.trim());
  if (missing.length) throw new Error('Missing signing credentials: ' + missing.join(', ') + '. See electron/docs/MAC-SIGNING.md.');
  const name = env.CSC_NAME.trim();
  const match = /^Developer ID Application:\s*(.+) \(([A-Z0-9]{10})\)$/.exec(name);
  if (!match) throw new Error('CSC_NAME must be the full Developer ID Application certificate name, including its Team ID; ad-hoc and Apple Development identities cannot sign this release.');
  const team = env.APPLE_TEAM_ID;
  if (!/^[A-Z0-9]{10}$/.test(team)) throw new Error('APPLE_TEAM_ID must be the 10-character Team ID in Apple Developer membership details, without surrounding spaces, not an enrollment ID.');
  if (match[2] !== team) throw new Error('The Developer ID Application certificate and APPLE_TEAM_ID belong to different teams. Check the selected membership before building.');
  const identity = name.replace(/^Developer ID Application:\s*/, '');
  return {
    extends: path.resolve(__dirname, '../electron-builder.yml'),
    forceCodeSigning: true,
    mac: { identity, type: 'distribution', notarize: true, hardenedRuntime: true, strictVerify: true },
  };
}

if (require.main === module) {
  (async () => {
    const config = releaseConfig(process.env);
    if (process.argv.includes('--check')) {
      console.log('Required credential fields are present. Certificate and Apple authorization are checked during the build.');
      return;
    }
    if (process.platform !== 'darwin') throw new Error('Build notarized Mac releases on a native macOS runner.');
    const { build, Platform, Arch } = require('electron-builder');
    await build({ targets: Platform.MAC.createTarget(['dmg', 'zip'], Arch[process.arch]), config, publish: 'never' });
  })().catch(error => {
    let message = error.message;
    for (const name of ['CSC_LINK', 'CSC_KEY_PASSWORD', 'APPLE_APP_SPECIFIC_PASSWORD']) {
      if (process.env[name]) message = message.split(process.env[name]).join('[redacted]');
    }
    console.error(message);
    process.exitCode = 1;
  });
}

module.exports = { releaseConfig };
