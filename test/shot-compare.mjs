/* A/B: render landing + survey at the current maximal comfort defaults vs a
 * neutral preset, to judge which reads more premium. Dev only. */
import { chromium } from 'playwright';
import http from 'http'; import { readFileSync, existsSync } from 'fs'; import path from 'path'; import { fileURLToPath } from 'url';
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const MIME={'.html':'text/html','.css':'text/css','.js':'application/javascript','.jsx':'text/babel','.json':'application/json','.svg':'image/svg+xml'};
const srv=http.createServer((q,s)=>{let p=decodeURIComponent((q.url||'/').split('?')[0]);if(p==='/')p='/index.html';const fp=path.join(ROOT,p);if(!existsSync(fp)){s.writeHead(404);return s.end('nf');}s.writeHead(200,{'content-type':MIME[path.extname(fp)]||'text/plain'});s.end(readFileSync(fp));});
await new Promise(r=>srv.listen(5599,r));
const b=await chromium.launch({args:['--ignore-certificate-errors']});
const RECS=[{title:'Data analyst',why:'You turn messy data into clear stories.',path:'SQL + an internship.'}];
async function go(label, comfort){
  const ctx=await b.newContext({viewport:{width:1440,height:900},deviceScaleFactor:2,ignoreHTTPSErrors:true});
  const pg=await ctx.newPage();
  await pg.route('**/api/**',r=>{const u=r.request().url();let d={ok:true};
    if(u.endsWith('/api/sessions'))d={id:'s1',persisted:true}; r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(d)});});
  if(comfort) await pg.addInitScript((c)=>{ try{ localStorage.setItem('thesis_comfort_v3', JSON.stringify(c)); }catch(e){} }, comfort);
  const T=(t,s='button')=>pg.locator(s,{hasText:t}).first();
  const settle=async(ms=400)=>{await pg.evaluate(()=>document.fonts&&document.fonts.ready);await pg.waitForTimeout(ms);};
  await pg.goto('http://localhost:5599/',{waitUntil:'networkidle'}); await pg.waitForSelector('.landing-hero',{timeout:20000}); await settle();
  await pg.screenshot({path:path.join(ROOT,'shots',`cmp-landing.${label}.png`)});
  await T('Begin').click(); await settle(150);
  await pg.locator('.consent-check input').check().catch(()=>{}); await T('I agree').click(); await settle(150);
  await pg.locator('.flow-body input').first().fill('Maya'); await T('Continue').click(); await settle(200);
  await pg.screenshot({path:path.join(ROOT,'shots',`cmp-survey1.${label}.png`)});
  // advance one page to the Big Five Likert
  await pg.evaluate(()=>{const set=(el,v)=>{const p=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,'value').set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));};
    document.querySelectorAll('input[type=number]').forEach(i=>set(i,'21'));
    document.querySelectorAll('.sv-choices').forEach(g=>g.querySelector('.sv-choice')?.click());
    document.querySelectorAll('textarea').forEach(t=>{if(!t.value)set(t,'Psychology');});});
  await pg.waitForTimeout(80);
  const btn=(await T('Done').count())?T('Done'):T('Continue'); if(await btn.count()&&!(await btn.isDisabled())){await btn.click(); await settle(200);}
  await pg.screenshot({path:path.join(ROOT,'shots',`cmp-likert.${label}.png`)});
  console.log('done', label);
  await ctx.close();
}
await go('current', null); // uses built-in COMFORT_DEFAULTS (xl/roomy/wide)
await go('neutral', { size:'md', spacing:'cozy', width:'normal', motion:'full', font:'sans' });
await b.close(); srv.close();
