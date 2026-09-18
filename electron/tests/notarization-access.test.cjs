const { test } = require('node:test');
const assert = require('node:assert/strict');
const { checkNotarization } = require('../build/check-notarization.cjs');
const credentials = {
  CSC_LINK: 'fixture-p12', CSC_KEY_PASSWORD: ' export password ',
  CSC_NAME: 'Developer ID Application: Fixture (TEAM123456)',
  APPLE_ID: ' fixture@example.invalid\n', APPLE_APP_SPECIFIC_PASSWORD: '\nfixture-apple-password\n',
  APPLE_TEAM_ID: 'TEAM123456',
};

test('notarization preflight checks access without submitting apps or logging history', () => {
  const message = checkNotarization(credentials, { platform: 'darwin', run: (command, args, options) => {
    assert.equal(command, '/usr/bin/xcrun');
    assert.deepEqual(args.slice(0, 2), ['notarytool', 'history']);
    assert.equal(args[args.indexOf('--apple-id') + 1], 'fixture@example.invalid');
    assert.equal(args[args.indexOf('--password') + 1], 'fixture-apple-password');
    assert.equal(args[args.indexOf('--team-id') + 1], 'TEAM123456');
    assert.equal(options.timeout, 60000);
    assert.equal(options.shell, undefined);
    return { status: 0, stdout: 'private submission history' };
  } });
  assert.match(message, /login verified/);
  assert.doesNotMatch(message, /private submission/);
  assert.equal(credentials.CSC_KEY_PASSWORD, ' export password ');
});

test('rejected credentials and tool errors surface safe actionable messages', () => {
  const cases = [
    [{ status: 1, stderr: 'HTTP status code: 401. fixture-apple-password' }, /HTTP 401/],
    [{ status: 1, stdout: 'HTTP status code: 403. fixture-apple-password' }, /HTTP 403/],
    [{ status: null, error: { code: 'ETIMEDOUT', message: 'fixture-apple-password' } }, /timed out/],
    [{ status: null, error: { code: 'ENOENT', message: 'fixture-apple-password' } }, /command-line tools/],
    [{ status: null, signal: 'SIGTERM', stderr: 'fixture-apple-password' }, /login check failed/],
  ];
  for (const [result, expected] of cases) {
    assert.throws(() => checkNotarization(credentials, { platform: 'darwin', run: () => result }), error => {
      assert.match(error.message, expected);
      assert.doesNotMatch(error.message, /fixture-apple-password/);
      return true;
    });
  }
});

test('invalid configuration and non-Mac hosts never start the notarization tool', () => {
  const run = () => { throw new Error('must not start'); };
  assert.throws(() => checkNotarization({ ...credentials, APPLE_TEAM_ID: 'wrong-team' }, { platform: 'darwin', run }), /10-character/);
  assert.throws(() => checkNotarization(credentials, { platform: 'win32', run }), /native macOS/);
});
