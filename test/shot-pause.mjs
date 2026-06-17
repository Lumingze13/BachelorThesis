/* Capture the "How it works" modal + a Pause screen (dev only). */
import { chromium } from 'playwright';
import http from 'http'; import { readFileSync, existsSync } from 'fs'; import path from 'path'; import { fileURLToPath } from 'url';
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const MIME={'.html':'text/html','.css':'text/css','.js':'application/javascript','.jsx':'text/babel','.json':'application/json','.svg':'image/svg+xml'};
const srv=http.createServer((q,s)=>{let p=decodeURIComponent((q.url||'/').split('?')[0]);if(p==='/')p='/index.html';const fp=path.join(ROOT,p);if(!existsSync(fp)){s.writeHead(404);return s.end('nf');}s.writeHead(200,{'content-type':MIME[path.extname(fp)]||'text/plain'});s.end(readFileSync(fp));});
await new Promise(r=>srv.listen(5599,r));
const b=await chromium.launch({args:['--ignore-certificate-errors']});
async function go(vp){
  const ctx=await b.newContext({viewport:{width:vp.w,height:vp.h},deviceScaleFactor:2,ignoreHTTPSErrors:true});
  const pg=await ctx.newPage();
  await pg.route('**/api/**',r=>{const u=r.request().url();let d={ok:true}; if(u.endsWith('/api/sessions'))d={id:'s1',persisted:true}; r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(d)});});
  const T=(t,s='button')=>pg.locator(s,{hasText:t}).first();
  const settle=async(ms=350)=>{await pg.evaluate(()=>document.fonts&&document.fonts.ready);await pg.waitForTimeout(ms);};
  await pg.goto('http://localhost:5599/',{waitUntil:'networkidle'}); await pg.waitForSelector('.landing-hero',{timeout:20000}); await settle();
  // How it works modal
  await T('How it works').click().catch(()=>{}); await settle();
  await pg.screenshot({path:path.join(ROOT,'shots',`howitworks.${vp.name}.png`)});
  // reset (the modal has no Escape handler) then walk to the first pause
  const safe=async(loc,ms=2500)=>{try{if(await loc.count())await loc.click({timeout:ms});}catch(e){}};
  try{
  await pg.goto('http://localhost:5599/',{waitUntil:'networkidle'}); await pg.waitForSelector('.landing-hero',{timeout:20000}); await settle(150);
  await safe(T('Begin')); await settle(150);
  await pg.screenshot({path:path.join(ROOT,'shots',`vrf-consent.${vp.name}.png`)});
  await pg.locator('.consent-check input').check().catch(()=>{}); await safe(T('I agree')); await settle(150);
  await pg.locator('.flow-body input').first().fill('Maya').catch(()=>{}); await safe(T('Continue')); await settle(200);
  for(let i=0;i<14;i++){ if(!(await pg.locator('.flow-progress').count()))break;
    if(i===0){ await pg.screenshot({path:path.join(ROOT,'shots',`vrf-survey.${vp.name}.png`)}); }
    await pg.evaluate(()=>{const set=(el,v)=>{const p=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,'value').set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));};
      document.querySelectorAll('input[type=number]').forEach(i=>set(i,'21'));
      document.querySelectorAll('.sv-choices').forEach(g=>g.querySelector('.sv-choice')?.click());
      document.querySelectorAll('.sv-multi').forEach(g=>g.querySelectorAll('.sv-choice').forEach((c,i)=>i<2&&c.click()));
      document.querySelectorAll('.sv-scale').forEach(s=>{const p=s.querySelectorAll('.sv-pt');p.length&&p[p.length-1].click();});
      document.querySelectorAll('.sv-ios').forEach(s=>{const o=s.querySelectorAll('.sv-ios-opt');o.length&&o[3].click();});
      document.querySelectorAll('textarea').forEach(t=>{if(!t.value)set(t,'A few honest words.');});});
    await pg.waitForTimeout(60);
    const btn=(await T('Done').count())?T('Done'):T('Continue'); if(!(await btn.count())||await btn.isDisabled())break;
    try{ await btn.click({timeout:2500}); }catch(e){ break; } await pg.waitForTimeout(80);
  }
  }catch(e){ console.log('walk err',vp.name,e.message); }
  await settle();
  await pg.screenshot({path:path.join(ROOT,'shots',`pause.${vp.name}.png`)});
  console.log('done',vp.name);
  await ctx.close();
}
await go({name:'laptop',w:1440,h:900});
await go({name:'mobile',w:390,h:844});
await b.close(); srv.close();
