const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { releaseConfig, normalizedAppleCredentials } = require('../build/notarized.cjs');
const credentials = { CSC_LINK: 'fixture-p12', CSC_KEY_PASSWORD: 'fixture-password', CSC_NAME: 'Developer ID Application: Fixture (TEAM123456)', APPLE_ID: 'fixture@example.invalid', APPLE_APP_SPECIFIC_PASSWORD: 'fixture-apple-password', APPLE_TEAM_ID: 'TEAM123456' };

test('release build cannot silently fall back to an unsigned or unnotarized package', () => {
  for (const name of Object.keys(credentials)) {
    const incomplete = { ...credentials }; delete incomplete[name];
    assert.throws(() => releaseConfig(incomplete), /Missing signing credentials/);
  }
  assert.throws(() => releaseConfig({ ...credentials, CSC_NAME: '-' }), /ad-hoc/);
  const config = releaseConfig(credentials);
  assert.equal(config.forceCodeSigning, true);
  assert.equal(config.mac.identity, 'Fixture (TEAM123456)');
  assert.equal(config.mac.type, 'distribution');
  assert.equal(config.mac.notarize, true);
  assert.equal(config.mac.hardenedRuntime, true);
});

test('electron-builder merges the release overrides over the ad-hoc defaults', async () => {
  const { getConfig, validateConfiguration } = require('app-builder-lib/out/util/config/config');
  const { DebugLogger } = require('builder-util');
  const config = await getConfig(path.resolve(__dirname, '..'), null, releaseConfig(credentials));
  await validateConfiguration(config, new DebugLogger());
  assert.equal(config.mac.identity, 'Fixture (TEAM123456)');
  assert.equal(config.mac.notarize, true);
  assert.equal(config.forceCodeSigning, true);
  assert.equal(config.mac.entitlements, 'entitlements.mac.plist');
  assert.deepEqual(config.mac.target, ['dmg', 'zip']);
});

test('wrong certificate types and mismatched teams fail before build downloads', () => {
  for (const name of ['Apple Development: Fixture (TEAM123456)', 'Developer ID Installer: Fixture (TEAM123456)', 'Fixture (TEAM123456)', 'Developer ID Application: Fixture']) {
    assert.throws(() => releaseConfig({ ...credentials, CSC_NAME: name }), /full Developer ID Application/);
  }
  assert.throws(() => releaseConfig({ ...credentials, APPLE_TEAM_ID: 'enrollment-id' }), /not an enrollment ID/);
  assert.throws(() => releaseConfig({ ...credentials, APPLE_TEAM_ID: 'OTHER12345' }), /different teams/);
  assert.throws(() => releaseConfig({ ...credentials, APPLE_TEAM_ID: ' TEAM123456 ' }), /without surrounding spaces/);
  assert.equal(releaseConfig({ ...credentials, CSC_NAME: ` ${credentials.CSC_NAME} ` }).mac.identity, 'Fixture (TEAM123456)');
});

test('a failed build stays failed after asynchronous temporary-file cleanup', () => {
  const wrapper = path.resolve(__dirname, '../build/notarized.cjs');
  const cleanup = require.resolve('async-exit-hook');
  const copied = { ...credentials, APPLE_ID: ` ${credentials.APPLE_ID}\r\n`,
    APPLE_APP_SPECIFIC_PASSWORD: ` \t${credentials.APPLE_APP_SPECIFIC_PASSWORD}\r\n`,
    CSC_KEY_PASSWORD: ' certificate password with significant outer spaces ' };
  const script = `
    const Module = require('node:module');
    Object.defineProperty(process, 'platform', { value: 'darwin' });
    const originalLoad = Module._load;
    Module._load = function (id, ...args) {
      if (id !== 'electron-builder') return originalLoad.call(this, id, ...args);
      return {
        Platform: { MAC: { createTarget: () => [] } }, Arch: { [process.arch]: 0 },
        build: async () => {
          require('node:assert/strict').equal(process.env.APPLE_ID, ${JSON.stringify(credentials.APPLE_ID)});
          require('node:assert/strict').equal(process.env.APPLE_APP_SPECIFIC_PASSWORD, ${JSON.stringify(credentials.APPLE_APP_SPECIFIC_PASSWORD)});
          require('node:assert/strict').equal(process.env.CSC_KEY_PASSWORD, ${JSON.stringify(copied.CSC_KEY_PASSWORD)});
          require(${JSON.stringify(cleanup)})(done => setImmediate(() => {
            process.stdout.write('cleanup completed\\n');
            done();
          }));
          throw new Error('Notarization refused: ' + process.env.APPLE_APP_SPECIFIC_PASSWORD + '; copied value: ' + ${JSON.stringify(copied.APPLE_APP_SPECIFIC_PASSWORD)});
        }
      };
    };
    process.argv = [process.execPath, ${JSON.stringify(wrapper)}];
    Module.runMain();
  `;
  const result = spawnSync(process.execPath, ['-e', script], {
    env: { ...process.env, ...copied }, encoding: 'utf8', timeout: 15000,
  });
  assert.ifError(result.error);
  assert.equal(result.signal, null);
  assert.match(result.stdout, /cleanup completed/);
  assert.match(result.stderr, /Notarization refused: \[redacted\]/);
  assert.match(result.stderr, /copied value: \[redacted\]/);
  assert.doesNotMatch(result.stderr, /fixture-apple-password/);
  assert.equal(result.status, 1, 'cleanup must not turn a rejected build into exit 0');
});

test('Apple credential normalization only removes copied outer whitespace', () => {
  const env = { ...credentials, APPLE_ID: ' fixture@example.invalid\r\n',
    APPLE_APP_SPECIFIC_PASSWORD: '\t fixture-apple-password \n', APPLE_TEAM_ID: ' TEAM123456 ',
    CSC_KEY_PASSWORD: ' significant spaces ' };
  assert.deepEqual(normalizedAppleCredentials(env), {
    APPLE_ID: credentials.APPLE_ID, APPLE_APP_SPECIFIC_PASSWORD: credentials.APPLE_APP_SPECIFIC_PASSWORD,
    APPLE_TEAM_ID: ' TEAM123456 ',
  });
  assert.equal(env.CSC_KEY_PASSWORD, ' significant spaces ');
  assert.equal(env.APPLE_APP_SPECIFIC_PASSWORD, '\t fixture-apple-password \n');
});
