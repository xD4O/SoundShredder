const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { releaseConfig } = require('../build/notarized.cjs');
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
