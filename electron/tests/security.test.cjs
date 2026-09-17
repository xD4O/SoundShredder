const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { loopback, sameOrigin, external } = require('../security.cjs');
const { request } = require('../backend.cjs');

test('engine addresses cannot redirect credentials to a different host', () => {
  for (const url of ['https://evil.test', 'file:///tmp/test', 'http://localhost:1234', 'http://127.0.0.1:1234@evil.test', 'http://evil.test:1234']) assert.equal(loopback(url), null);
  assert.ok(sameOrigin('http://127.0.0.1:3456/?session=1', 'http://127.0.0.1:3456'));
  assert.equal(sameOrigin('http://127.0.0.1:3457/', 'http://127.0.0.1:3456'), false);
});
test('only expected HTTPS community and project links can leave the app', () => {
  assert.ok(external('https://github.com/xD4O/SoundShredder/releases'));
  for (const url of ['file:///C:/Windows', 'ms-settings:', 'javascript:alert(1)', 'https://github.com.evil.test/', 'https://user:pass@github.com/', 'http://github.com/']) assert.equal(external(url), false);
});
test('local lifecycle client refuses redirects', async () => {
  const server = http.createServer((_req, res) => { res.writeHead(302, { Location: 'https://example.invalid/' }); res.end('{}'); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try { await assert.rejects(request(`http://127.0.0.1:${server.address().port}/`, 'private'), /Engine request failed/); }
  finally { await new Promise(resolve => server.close(resolve)); }
});
