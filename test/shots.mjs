/* Visual screenshot harness (dev only — not part of npm test).
 * Serves the repo, mocks /api, drives the flow in real Chromium, and writes
 * above-the-fold PNGs per screen × viewport so we can see the actual UI.
 * Usage: node test/shots.mjs [screens...]   (default: all)
 */
import { chromium } from 'playwright';
import http from 'http';
import { readFileSync, existsSync, mkdirSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const OUT = path.join(ROOT, 'shots');
mkdirSync(OUT, { recursive: true });
const PORT = 5599;
const MIME = { '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript', '.jsx': 'text/babel', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png' };

const server = http.createServer((req, res) => {
  let p = decodeURIComponent((req.url || '/').split('?')[0]);
  if (p === '/') p = '/index.html';
  const fp = path.join(ROOT, p);
  if (!fp.startsWith(ROOT) || !existsSync(fp)) { res.writeHead(404); return res.end('not found'); }
  res.writeHead(200, { 'content-type': MIME[path.extname(fp)] || 'text/plain' });
  res.end(readFileSync(fp));
});
await new Promise((r) => server.listen(PORT, r));
const BASE = `http://localhost:${PORT}/`;

const VIEWPORTS = [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'laptop', width: 1440, height: 900 },
  { name: 'desktop', width: 1920, height: 1200 },
];

const RECS = [
  { title: 'Data analyst', why: 'You like turning messy data into clear, honest stories people can act on.', path: 'Pick up SQL + one stats course, then an analytics internship.' },
  { title: 'Product manager', why: 'You organise people and ideas and keep the through-line in view.', path: 'Join an APM programme; ship one small side project end to end.' },
  { title: 'UX researcher', why: 'You are curious about why people do what they do, and patient enough to find out.', path: 'Run two guerrilla studies; build a small portfolio of write-ups.' },
];

async function mock(page) {
  await page.route('**/api/**', (route) => {
    const u = route.request().url();
    let body = { ok: true };
    if (u.includes('/api/phase-b/session')) body = { sessionId: 'pb1', opening: 'Welcome — before we step into the conversation, what in your studies genuinely pulls you in right now?' };
    else if (u.includes('/api/phase-c/session')) body = { sessionId: 'pc1', opening: "Hey — it's me. You, ten years on.\n\nI still remember sitting exactly where you are. What's on your mind today?" };
    else if (u.includes('/api/chat')) body = { reply: "That makes sense — and honestly, it's the same instinct that got me here.\n\nWhen I was deciding, I kept waiting to feel certain. What actually helped was treating the next step as an experiment, not a vow.", recommendations: RECS };
    else if (u.includes('/api/validate-career')) body = { ok: true };
    else if (u.endsWith('/api/sessions')) body = { id: 's1', condition: 'main', persisted: true };
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
}

const T = (page, text, sel = 'button') => page.locator(sel, { hasText: text }).first();
const settle = async (page, ms = 350) => { await page.evaluate(() => document.fonts && document.fonts.ready); await page.waitForTimeout(ms); };

async function autofillPage(page) {
  await page.evaluate(() => {
    const set = (el, v) => { const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v); el.dispatchEvent(new Event('input', { bubbles: true })); };
    document.querySelectorAll('input[type=number]').forEach((i) => set(i, '21'));
    document.querySelectorAll('.sv-choices').forEach((g) => { if (!g.querySelector('.sv-choice.on')) g.querySelector('.sv-choice')?.click(); });
    document.querySelectorAll('.sv-multi').forEach((g) => g.querySelectorAll('.sv-choice').forEach((c, i) => i < 3 && c.click()));
    document.querySelectorAll('.sv-scale').forEach((s) => { const p = s.querySelectorAll('.sv-pt'); p.length && p[p.length - 1].click(); });
    document.querySelectorAll('.sv-ios').forEach((s) => { const o = s.querySelectorAll('.sv-ios-opt'); o.length && o[3].click(); });
    document.querySelectorAll('textarea').forEach((t) => { if (!t.value && !t.disabled) set(t, 'A few honest words for the record.'); });
  });
}

async function run(vp) {
  const ctx = await chromium.launchPersistentContext('', { viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1 }).catch(() => null);
  return ctx;
}

// The remote network uses a TLS-intercepting proxy whose CA Chromium doesn't
// trust, so the CDN (react/babel/fonts) is rejected without these.
const browser = await chromium.launch({ args: ['--ignore-certificate-errors'] });
const want = process.argv.slice(2);
const pick = (name) => !want.length || want.includes(name);

for (const vp of VIEWPORTS) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1, ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await mock(page);
  const shot = async (name) => { await settle(page); await page.screenshot({ path: path.join(OUT, `${name}.${vp.name}.png`) }); console.log('  ✓', `${name}.${vp.name}`); };
  try {
    await page.goto(BASE, { waitUntil: 'networkidle' });
    await page.waitForSelector('.landing-hero, .flow, .app', { timeout: 20000 });
    if (pick('landing')) await shot('01-landing');

    await T(page, 'Begin').click(); await settle(page);
    if (pick('consent')) await shot('02-consent');

    await page.locator('.consent-check input').check().catch(() => {});
    await T(page, 'I agree').click(); await settle(page);
    if (pick('avatar')) await shot('03-avatar');

    await page.locator('.flow-body input').first().fill('Maya'); await settle(page, 150);
    await T(page, 'Continue').click(); await settle(page);

    // Pre-survey pages — screenshot the first, then autofill through to Phase B.
    let pageNo = 0;
    while (await page.locator('.flow-progress').count() && pageNo < 14) {
      if (pageNo === 0 && pick('survey')) await shot('04-survey');
      if (pageNo === 1 && pick('survey2')) await shot('04b-survey');
      await autofillPage(page); await page.waitForTimeout(60);
      const btn = (await T(page, 'Done').count()) ? T(page, 'Done') : T(page, 'Continue');
      if (!(await btn.count()) || await btn.isDisabled()) break;
      await btn.click(); await page.waitForTimeout(80);
      pageNo++;
    }

    if (await T(page, 'Continue').count()) { await T(page, 'Continue').click(); await settle(page); } // pause A→B
    if (pick('phaseb')) await shot('05-phaseb');

    await page.locator('.pb-composer textarea').fill('I like turning messy data into clear stories people actually use.').catch(() => {});
    await page.locator('.pb-composer .send').click().catch(() => {});
    await page.waitForTimeout(500);
    if (pick('phaseb-recs')) await shot('06-phaseb-recs');
    await page.locator('.rec-card').first().click().catch(() => {});
    await page.waitForTimeout(200);
    await page.evaluate(() => document.querySelectorAll('.pb-lock .sv-scale').forEach((s) => { const p = s.querySelectorAll('.sv-pt'); p.length && p[p.length - 1].click(); }));
    await settle(page);
    if (pick('phaseb-lock')) await shot('07-phaseb-lock');
    if (await T(page, 'Step into this future').count()) { await T(page, 'Step into this future').click(); await page.waitForTimeout(300); }
    if (await T(page, 'Begin').count()) { await T(page, 'Begin').click(); await page.waitForTimeout(400); } // pause B→C
    if (pick('chat')) await shot('08-chat');
  } catch (e) {
    console.error(`  ✗ [${vp.name}]`, e.message);
  }
  await ctx.close();
}
await browser.close();
server.close();
console.log('\nShots in', OUT);
