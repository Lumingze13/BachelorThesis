/* Preview-vs-real parity test.
 *
 * A researcher "preview" run (?preview=1, minted from the admin Recruit tab) must
 * show EXACTLY the same screens, survey pages and question wording as the real
 * participant app for the same cell — the only sanctioned differences are that
 * preview skips gates, saves nothing, and shows a PREVIEW badge (none of which
 * change participant-visible content).
 *
 * For every launch cell (shared / k-base / a-refl / custom) this loads the whole
 * no-build bundle into a fresh jsdom twice — once as a preview link, once as a
 * real participant link — walks the entire flow filling everything identically,
 * fingerprints every screen + survey page (titles, question stems, choices), and
 * asserts the two fingerprint streams are identical. Run: node test/preview_parity_test.cjs
 */
const path = require('path');
const babel = require('@babel/core');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..');
const FILES = ['tweaks-panel.jsx', 'graphics.jsx', 'screens.jsx', 'survey.jsx', 'chat.jsx', 'phaseb.jsx', 'app.jsx'];
const compiled = FILES.map((f) => babel.transformFileSync(path.join(ROOT, f), { presets: [['@babel/preset-react']] }).code);

const tick = (ms = 40) => new Promise((r) => setTimeout(r, ms));
const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();

// Walk the full flow for one URL and return an ordered content fingerprint.
async function runFlow(url) {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>',
    { runScripts: 'outside-only', pretendToBeVisual: true, url });
  const { window } = dom;
  global.window = window; global.document = window.document; global.navigator = window.navigator;
  global.IS_REACT_ACT_ENVIRONMENT = false; window.IS_REACT_ACT_ENVIRONMENT = false;
  // react-dom feature-detects the DOM at require time, so it MUST be required
  // fresh against this run's window (re-using one instance across jsdom windows
  // wedges its input-event polyfill). Clear the cache and re-require per run.
  Object.keys(require.cache).forEach((k) => { if (/node_modules[\\/](react|react-dom|scheduler)[\\/]/.test(k)) delete require.cache[k]; });
  window.React = require('react');
  window.ReactDOM = require('react-dom');
  window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
  window.scrollTo = () => {};
  window.THESIS_TEST_NO_HOLD = true; // skip the imagination page's timed hold
  window.URL.createObjectURL = () => 'blob:stub';
  window.URL.revokeObjectURL = () => {};
  window.fetch = async (u, opts) => {
    const method = (opts && opts.method) || 'GET';
    let data = {};
    if (u.endsWith('/api/phase-b/session')) data = { sessionId: 'pb1', opening: 'Welcome! What in your studies genuinely pulls you in?' };
    else if (u.endsWith('/api/phase-c/session')) data = { sessionId: 'pc1', opening: "Hey — it's me, you in ten years.\n\nWhat's on your mind?" };
    else if (u.endsWith('/api/chat')) data = { reply: 'Here is a grounded reply.\n\nWhat else?', recommendations: [{ title: 'Data analyst', why: 'You like turning data into stories.', path: 'SQL plus an internship.' }, { title: 'Product manager', why: 'You organise people well.', path: 'APM programmes.' }] };
    else if (u.endsWith('/api/regenerate')) data = { reply: 'A rephrased reply.' };
    else if (u.endsWith('/api/validate-career')) data = { ok: true };
    else if (u.endsWith('/api/sessions') && method === 'POST') data = { id: 'sess-test', condition: 'main', persisted: true };
    else if (/\/api\/sessions\//.test(u)) data = { ok: true, status: 'in_progress', persisted: true };
    return { ok: true, status: 200, json: async () => data };
  };

  const doc = window.document;
  const $ = (sel, ctx = doc) => [...ctx.querySelectorAll(sel)];
  const click = (el) => el && el.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  const byText = (text, sel = 'button') => $(sel).find((b) => norm(b.textContent).includes(text));
  function setInput(el, value) {
    const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
    el.dispatchEvent(new window.Event('input', { bubbles: true }));
  }
  function autofill() {
    $('input[type=number]').forEach((i) => setInput(i, '21'));
    $('.sv-choices').forEach((g) => { if (!g.querySelector('.sv-choice.on')) click(g.querySelector('.sv-choice')); });
    $('.sv-multi').forEach((g) => g.querySelectorAll('.sv-choice').forEach((c, i) => { if (i < 3) click(c); }));
    $('.sv-scale').forEach((s) => { const pts = s.querySelectorAll('.sv-pt'); if (pts.length) click(pts[pts.length - 1]); });
    $('.sv-ios').forEach((s) => { const o = s.querySelectorAll('.sv-ios-opt'); if (o.length) click(o[3]); });
    $('textarea').forEach((t) => { if (!t.value && !t.disabled) setInput(t, 'a test answer'); });
  }
  // Content fingerprint of the survey page on screen now: page title, intro,
  // every question stem, and every choice label. Deliberately ignores the
  // progress counter and the (preview-only) PREVIEW badge.
  function pageFP() {
    const parts = [];
    $('.sv-wrap .sv-eyebrow, .sv-wrap h2').forEach((e) => parts.push('T:' + norm(e.textContent)));
    $('.sv-wrap .sv-intro').forEach((e) => parts.push('I:' + norm(e.textContent)));
    $('.sv-wrap .sv-stem, .sv-wrap .sv-scale-text, .sv-wrap .sv-label').forEach((e) => parts.push('Q:' + norm(e.textContent)));
    $('.sv-wrap .sv-choice').forEach((e) => parts.push('C:' + norm(e.textContent)));
    return parts.join(' | ');
  }

  for (const code of compiled) window.eval(code);
  await tick(60);

  const fp = [];
  fp.push('LANDING:' + (/Talk to/i.test(doc.body.textContent) ? 'ok' : 'MISSING'));
  click(byText('Begin')); await tick();
  fp.push('CONSENT:' + (/Informed consent/i.test(doc.body.textContent) ? 'ok' : 'MISSING'));
  const cc = doc.querySelector('.consent-check input'); if (cc) click(cc); await tick();
  click(byText('I agree')); await tick();

  fp.push('AVATAR:' + (byText('STEP 01', '.step-label') ? 'ok' : 'MISSING'));
  const nameInput = doc.querySelector('.flow-body input'); if (nameInput) setInput(nameInput, 'Maya'); await tick();
  click(byText('Continue')); await tick();

  let pre = 0;
  while (doc.querySelector('.flow-progress') && pre < 15) {
    fp.push('PRE#' + (pre + 1) + ' ' + pageFP());
    autofill(); await tick();
    const btn = byText('Done') || byText('Continue');
    if (!btn || btn.disabled) { fp.push('PRE#' + (pre + 1) + ':STUCK'); break; }
    click(btn); await tick();
    pre++;
  }
  fp.push('PRE_COUNT:' + pre);

  await tick();
  click(byText('Continue')); await tick(60); // pause A→B

  await tick(60);
  fp.push('PHASEB:' + (doc.querySelector('.pb-wrap') ? 'ok' : 'MISSING'));
  const pbc = doc.querySelector('.pb-composer textarea'); if (pbc) setInput(pbc, 'I like turning messy data into clear stories.'); await tick();
  const send = doc.querySelector('.pb-composer .send'); if (send) click(send); await tick(80);
  const cards = $('.rec-card'); if (cards.length) click(cards[0]); await tick();
  fp.push('PHASEB_LOCK:' + (doc.querySelector('.pb-lock') ? 'ok' : 'MISSING'));
  $('.pb-lock .sv-scale').forEach((s) => { const pts = s.querySelectorAll('.sv-pt'); if (pts.length) click(pts[pts.length - 1]); }); await tick();
  const stepBtn = byText('Step into this future'); if (stepBtn) click(stepBtn); await tick(80);

  click(byText('Begin')); await tick(80); // pause B→C

  fp.push('PHASEC:' + (doc.querySelector('.chat-app') ? 'ok' : 'MISSING'));
  click(byText('Finish')); await tick();
  click(byText('Continue')); await tick(); // pause C→post

  let post = 0;
  while (doc.querySelector('.flow-progress') && post < 12) {
    fp.push('POST#' + (post + 1) + ' ' + pageFP());
    autofill(); await tick();
    const btn = byText('Done') || byText('Continue');
    if (!btn || btn.disabled) { fp.push('POST#' + (post + 1) + ':STUCK'); break; }
    click(btn); await tick();
    post++;
  }
  fp.push('POST_COUNT:' + post);

  await tick();
  fp.push('HUB:' + (byText('Keep talking') ? 'ok' : 'MISSING'));

  return { fp, pre, post };
}

const MODES = [
  { key: 'shared', cond: 'main',     rec: 'direct',     study: 'shared',  pid: 'S001' },
  { key: 'k-base', cond: 'baseline', rec: 'direct',     study: 'kangzhi', pid: 'K001' },
  { key: 'a-refl', cond: 'main',     rec: 'reflective', study: 'andrea',  pid: 'A001' },
  { key: 'custom', cond: 'baseline', rec: 'guide',      study: 'kangzhi', pid: 'X001' },
];
const previewUrl = (m) => `http://localhost/?cond=${m.cond}&rec=${m.rec}&study=${m.study}&preview=1`;
const realUrl = (m) => `http://localhost/?session=sess-test&cond=${m.cond}&rec=${m.rec}&study=${m.study}&pid=${m.pid}`;

const fail = (msg) => { console.error('✗ ' + msg); process.exitCode = 1; };
const ok = (msg) => console.log('✓ ' + msg);

(async () => {
  const postCounts = {};
  for (const m of MODES) {
    const real = await runFlow(realUrl(m));
    const prev = await runFlow(previewUrl(m));
    postCounts[m.key] = real.post;

    // Sanity: each variant actually reached the end of the flow.
    if (!(real.fp.includes('HUB:ok') && prev.fp.includes('HUB:ok'))) {
      fail(`[${m.key}] a variant did not reach the post-study hub (real=${real.post}p, preview=${prev.post}p)`);
      continue;
    }

    // Core assertion: identical content fingerprint, screen by screen.
    const n = Math.max(real.fp.length, prev.fp.length);
    let firstDiff = -1;
    for (let i = 0; i < n; i++) {
      if (real.fp[i] !== prev.fp[i]) { firstDiff = i; break; }
    }
    if (firstDiff !== -1) {
      fail(`[${m.key}] preview diverges from real at step ${firstDiff}:`);
      console.error('    real    : ' + (real.fp[firstDiff] || '(end)'));
      console.error('    preview : ' + (prev.fp[firstDiff] || '(end)'));
    } else if (real.fp.length !== prev.fp.length) {
      fail(`[${m.key}] preview has ${prev.fp.length} steps, real has ${real.fp.length}`);
    } else {
      ok(`[${m.key}] preview matches real exactly — ${real.fp.length} steps, pre=${real.pre}p post=${real.post}p`);
    }
  }

  // Cross-mode: the study tag no longer changes the page set (Andrea's MC page
  // was dropped), so every cell must yield the same post-survey page count.
  const counts = [...new Set(Object.values(postCounts))];
  if (counts.length === 1) {
    ok(`Post-survey page count is uniform across all study tags: ${counts[0]} pages (Andrea MC removal verified)`);
  } else {
    fail(`Post-survey page count differs across modes: ${JSON.stringify(postCounts)}`);
  }

  if (process.exitCode) { console.error('\nPREVIEW PARITY TEST FAILED ❌'); process.exit(1); }
  console.log('\nPREVIEW PARITY TEST PASSED ✅');
  process.exit(0);
})().catch((e) => { console.error('\nPREVIEW PARITY TEST ERROR:', e.stack || e.message); process.exit(1); });
