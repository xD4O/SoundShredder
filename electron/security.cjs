'use strict';
function loopback(value) {
  try {
    const u = new URL(value);
    return u.protocol === 'http:' && u.hostname === '127.0.0.1' && !!u.port && !u.username && !u.password ? u : null;
  } catch { return null; }
}
function sameOrigin(value, base) {
  const a = loopback(value), b = loopback(base);
  return !!a && !!b && a.origin === b.origin;
}
function external(value) {
  try {
    const u = new URL(value);
    return u.protocol === 'https:' && !u.username && !u.password &&
      ['github.com', 'higgsfield.ai', 'x.com', 'www.instagram.com', 'www.youtube.com'].includes(u.hostname);
  } catch { return false; }
}
module.exports = { loopback, sameOrigin, external };
