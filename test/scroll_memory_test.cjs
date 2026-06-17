/* Scroll-behaviour test: proves the app (a) opens every screen at the very top
 * on first view, (b) never scrolls except in response to a user navigation, and
 * (c) restores the exact scroll offset when the participant returns to a screen.
 * Run: node test/scroll_memory_test.cjs */
const fs = require('fs');
const path = require('path');
const babel = require('@babel/core');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..');
const FILES = ['tweaks-panel.jsx', 'graphics.jsx', 'screens.jsx', 'survey.jsx', 'chat.jsx', 'phaseb.jsx', 'app.jsx'];

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>',
  { runScripts: 'outside-only', pretendToBeVisual: true, url: 'http://localhost/?condition=main' });
const { window } = dom;
global.window = window; global.document = window.document; global.navigator = window.navigator;
global.IS_REACT_ACT_ENVIRONMENT = false; window.IS_REACT_ACT_ENVIRONMENT = false;
window.React = require('react');
window.ReactDOM = require('react-dom');
window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
window.THESIS_TEST_NO_HOLD = true;
window.URL.createObjectURL = () => 'blob:stub';
window.URL.revokeObjectURL = () => {};
window.fetch = async () => ({ ok: true, status: 200, json: async () => ({}) });

// Controllable scroll position: scrollTo records every call and moves a virtual
// offset that scrollY reads back (jsdom has no layout, so we model it).
const scrollCalls = [];
let _y = 0;
window.scrollTo = (x, y) => { _y = y | 0; scrollCalls.push(_y); };
Object.defineProperty(window, 'scrollY', { configurable: true, get: () => _y });
Object.defineProperty(window, 'pageYOffset', { configurable: true, get: () => _y });

const tick = (ms = 40) => new Promise((r) => setTimeout(r, ms));
const $ = (sel) => [...window.document.querySelectorAll(sel)];
const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();
const click = (el) => el && el.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
const byText = (text, sel = 'button') => $(sel).find((b) => norm(b.textContent).includes(text));
// Simulate the user scrolling the window down to offset y.
const userScrollTo = (y) => { _y = y; window.dispatchEvent(new window.Event('scroll')); };

const fail = (m) => { console.error('✗ ' + m); process.exitCode = 1; };
const ok = (m) => console.log('✓ ' + m);

(async () => {
  for (const f of FILES) window.eval(babel.transformFileSync(path.join(ROOT, f), { presets: [['@babel/preset-react']] }).code);
  await tick(60);

  // Mount → landing. The screen-enter effect must put us at the top.
  if (!/Talk to/i.test(window.document.body.textContent)) return fail('Landing did not render');
  if (_y !== 0) fail(`Landing should open at top, scrollY=${_y}`); else ok('Landing opens at the top');

  // Landing → consent (first visit): must open at the top.
  scrollCalls.length = 0;
  click(byText('Begin')); await tick();
  if (!/Informed consent/i.test(window.document.body.textContent)) return fail('Consent did not render');
  const firstY = scrollCalls.length ? scrollCalls[scrollCalls.length - 1] : _y;
  if (firstY !== 0) fail(`Consent (first visit) should open at top, got ${firstY}`); else ok('New screen opens at the top (no mid-page jump)');

  // User scrolls down the consent page, then leaves.
  userScrollTo(260); await tick();

  // Consent → landing (Back). Landing was never scrolled, so it returns to top.
  scrollCalls.length = 0;
  click(byText('Back')); await tick();
  const backY = scrollCalls.length ? scrollCalls[scrollCalls.length - 1] : _y;
  if (backY !== 0) fail(`Returning to unscrolled Landing should be top, got ${backY}`); else ok('Returning to an unscrolled screen stays at the top');

  // Landing → consent again: must restore the 260px offset we left it at.
  scrollCalls.length = 0;
  click(byText('Begin')); await tick();
  const restored = scrollCalls.length ? scrollCalls[scrollCalls.length - 1] : _y;
  if (restored !== 260) fail(`Returning to Consent should restore scrollY=260, got ${restored}`);
  else ok('Returning to a screen restores the exact offset it was left at (260px)');

  // No autofocus/scrollIntoView-style auto-scroll: while sitting on a screen with
  // no user navigation, nothing should move the page on its own.
  _y = 80; // pretend the user is mid-page
  const before = scrollCalls.length;
  await tick(80);
  if (scrollCalls.length !== before) fail('Page auto-scrolled with no user navigation'); else ok('No auto-scroll without a user navigation');

  if (process.exitCode) { console.error('\nSCROLL MEMORY TEST FAILED ❌'); process.exit(1); }
  console.log('\nSCROLL MEMORY TEST PASSED ✅');
  process.exit(0);
})().catch((e) => { console.error('\nSCROLL MEMORY TEST ERROR:', e.stack || e.message); process.exit(1); });
