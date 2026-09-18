'use strict';
const { spawnSync } = require('node:child_process');
const { releaseConfig, normalizedAppleCredentials } = require('./notarized.cjs');

function checkNotarization(env, { platform = process.platform, run = spawnSync } = {}) {
  const credentials = normalizedAppleCredentials(env);
  releaseConfig({ ...env, ...credentials });
  if (platform !== 'darwin') throw new Error('Check Apple notarization access on a native macOS runner.');
  const result = run('/usr/bin/xcrun', [
    'notarytool', 'history', '--apple-id', credentials.APPLE_ID,
    '--password', credentials.APPLE_APP_SPECIFIC_PASSWORD,
    '--team-id', credentials.APPLE_TEAM_ID, '--output-format', 'json',
  ], { encoding: 'utf8', timeout: 60000, maxBuffer: 2 * 1024 * 1024 });
  // Never print subprocess output or its error object: these may contain credentials.
  if (result.error?.code === 'ETIMEDOUT') {
    throw new Error('Apple notarization login check timed out after 60 seconds. Retry when the service is reachable.');
  }
  if (result.error) throw new Error('Unable to run the Apple notarization login check. Ensure Xcode command-line tools are installed.');
  if (result.status !== 0) {
    const output = `${result.stdout || ''}\n${result.stderr || ''}`;
    if (/\b401\b|invalid credentials|unauthenticated/i.test(output)) {
      throw new Error('Apple rejected notarization credentials (HTTP 401). APPLE_ID and APPLE_APP_SPECIFIC_PASSWORD must belong to the same Apple account. Update the app-specific password in GitHub Actions secrets; do not use the normal Apple password.');
    }
    if (/\b403\b|forbidden/i.test(output)) {
      throw new Error('Apple denied notarization access (HTTP 403). Check this account\'s team membership and any pending developer agreements.');
    }
    throw new Error('Apple notarization login check failed. Check Apple service availability and the repository signing secrets.');
  }
  return 'Apple notarization login verified. No application was submitted.';
}

if (require.main === module) {
  try {
    console.log(checkNotarization(process.env));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}

module.exports = { checkNotarization };
