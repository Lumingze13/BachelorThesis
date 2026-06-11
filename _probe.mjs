import { chromium } from 'playwright';

const BASE = 'http://localhost:3457';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
await page.goto(BASE + '/?cond=main', { waitUntil: 'networkidle' });
await page.waitForTimeout(1200);

// 1. How-it-works modal opens and closes
await page.click('nav .btn');
await page.waitForTimeout(400);
await page.screenshot({ path: '/tmp/ui/probe_how_modal.png' });
const modalOpen = await page.evaluate(() => !!document.querySelector('.how-modal'));
await page.click('.how-close');
await page.waitForTimeout(300);
const modalClosed = await page.evaluate(() => !document.querySelector('.how-modal'));
console.log('how modal open/close:', modalOpen, modalClosed);

// 2. Comfort panel on a flow screen (lifted fab): open, screenshot, close via fab
await page.evaluate(() => document.querySelectorAll('.hero-ctas .btn')[0].click()); // Begin -> consent (flow-foot present)
await page.waitForTimeout(500);
await page.click('.comfort-fab');
await page.waitForTimeout(400);
await page.screenshot({ path: '/tmp/ui/probe_comfort_open.png' });
const fabClickable = await page.evaluate(() => {
  const fab = document.querySelector('.comfort-fab');
  const r = fab.getBoundingClientRect();
  const el = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return el === fab || fab.contains(el);
});
await page.click('.comfort-fab'); // must close it again
await page.waitForTimeout(300);
const panelClosed = await page.evaluate(() => !document.querySelector('.comfort-panel'));
console.log('comfort: fab clickable while open =', fabClickable, '| closes via fab =', panelClosed);

// 3. default comfort size is xl
const size = await page.evaluate(() => document.documentElement.dataset.size);
console.log('default size:', size);

await browser.close();
