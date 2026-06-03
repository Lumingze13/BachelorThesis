/*
 * Admin auth-gate test: mounts the admin routes on a throwaway Express app and
 * checks the gate without booting the main server. Needs ADMIN_TOKEN set
 * (loaded from .env). DB-backed assertions are conditional on DATABASE_URL.
 */
import assert from 'node:assert';
import express from 'express';
import { mountAdminRoutes } from '../lib/admin_routes.js';
import { dbEnabled, closePool } from '../lib/db.js';

if (!process.env.ADMIN_TOKEN) {
  console.log('• ADMIN_TOKEN not set — skipping admin gate test');
  process.exit(0);
}
const TOKEN = process.env.ADMIN_TOKEN;

const app = express();
app.use(express.json());
mountAdminRoutes(app);
const server = app.listen(0);
await new Promise((r) => server.once('listening', r));
const base = `http://127.0.0.1:${server.address().port}`;

// 1. unauthenticated API -> 401
assert.equal((await fetch(`${base}/api/admin/sessions`)).status, 401, 'unauth API should be 401');
console.log('✓ /api/admin/* without token → 401');

// 2. /admin without cookie -> login page
const loginPage = await (await fetch(`${base}/admin`)).text();
assert.ok(/Sign in/i.test(loginPage), '/admin without auth should serve login');
console.log('✓ /admin without token → login page (no data)');

// 3. wrong token -> 401
assert.equal((await fetch(`${base}/admin/login`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: 'nope' }),
})).status, 401, 'wrong token should be 401');
console.log('✓ wrong token → 401');

// 4. correct token -> sets cookie
const ok = await fetch(`${base}/admin/login`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: TOKEN }),
});
assert.equal(ok.status, 200, 'correct token should be 200');
assert.ok(/admin_token=/.test(ok.headers.get('set-cookie') || ''), 'should set admin_token cookie');
console.log('✓ correct token → 200 + cookie');

// 5. bearer token authorizes (200 if DB, else 503)
const authed = await fetch(`${base}/api/admin/sessions`, { headers: { Authorization: `Bearer ${TOKEN}` } });
assert.ok(authed.status === 200 || authed.status === 503, `authed list should be 200/503, got ${authed.status}`);
console.log(`✓ bearer token authorized (status ${authed.status}${dbEnabled ? '' : ' — DB disabled'})`);

server.close();
await closePool();
console.log('\nADMIN GATE TESTS PASSED ✅');
