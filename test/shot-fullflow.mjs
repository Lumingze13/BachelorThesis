/* Full-flow screenshot sweep to closure (dev only). Walks the whole study with
 * the API mocked, autofilling each step, and captures the screens not covered by
 * the other harnesses: the "imagine" page, the new 6-item CIP survey page,
 * post-survey, the explore hub, and the closure. */
import { chromium } from 'playwright';
import http from 'http'; import { readFileSync, existsSync, mkdirSync } from 'fs'; import path from 'path'; import { fileURLToPath } from 'url';
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
mkdirSync(path.join(ROOT, 'shots'), { recursive: true });
const MIME={'.html':'text/html','.css':'text/css','.js':'application/javascript','.jsx':'text/babel','.json':'application/json','.svg':'image/svg+xml'};
const srv=http.createServer((q,s)=>{let p=decodeURIComponent((q.url||'/').split('?')[0]);if(p==='/')p='/index.html';const fp=path.join(ROOT,p);if(!existsSync(fp)){s.writeHead(404);return s.end('nf');}s.writeHead(200,{'content-type':MIME[path.extname(fp)]||'text/plain'});s.end(readFileSync(fp));});
await new Promise(r=>srv.listen(5599,r));
const RECS=[{title:'Data analyst',why:'Turn messy data into clear stories.',path:'SQL + an internship.'},{title:'UX researcher',why:'Curious about why people act.',path:'Run two studies.'}];
const b=await chromium.launch({args:['--ignore-certificate-errors']});
const ctx=await b.newContext({viewport:{width:1280,height:880},deviceScaleFactor:1,ignoreHTTPSErrors:true});
const pg=await ctx.newPage();
const errs=[]; pg.on('pageerror',e=>errs.push('PAGEERROR '+e.message.slice(0,160)));
await pg.route('**/api/**',r=>{const u=r.request().url();let d={ok:true};
  if(u.includes('/api/phase-b/session'))d={sessionId:'pb1',opening:'Before we step in — what pulls you in right now?'};
  else if(u.includes('/api/phase-c/session'))d={sessionId:'pc1',opening:"Hey — it's me. You, ten years on. What's on your mind?"};
  else if(u.includes('/api/chat'))d={reply:"That tracks. When I was deciding I treated the next step as an experiment, not a vow.",recommendations:RECS};
  else if(u.includes('/api/validate-career'))d={ok:true};
  else if(u.endsWith('/api/sessions'))d={id:'s1',condition:'main',persisted:true};
  r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(d)});});
const T=(t,s='button')=>pg.locator(s,{hasText:t}).first();
const settle=async(ms=350)=>{await pg.evaluate(()=>document.fonts&&document.fonts.ready);await pg.waitForTimeout(ms);};
const shot=async(n)=>{await settle();await pg.screenshot({path:path.join(ROOT,'shots',`ff-${n}.png`)});console.log('  ✓ ff-'+n);};
const safe=async(loc,ms=3000)=>{try{if(await loc.count()&&await loc.isEnabled())await loc.click({timeout:ms});}catch(e){}};
const autofill=async()=>pg.evaluate(()=>{const set=(el,v)=>{const p=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,'value').set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));};
  document.querySelectorAll('input[type=number]').forEach(i=>set(i,'21'));
  document.querySelectorAll('.sv-choices').forEach(g=>{if(!g.querySelector('.sv-choice.on'))g.querySelector('.sv-choice')?.click();});
  document.querySelectorAll('.sv-multi').forEach(g=>g.querySelectorAll('.sv-choice').forEach((c,i)=>i<2&&c.click()));
  document.querySelectorAll('.sv-scale').forEach(s=>{const p=s.querySelectorAll('.sv-pt');p.length&&p[p.length-1].click();});
  document.querySelectorAll('.sv-ios').forEach(s=>{const o=s.querySelectorAll('.sv-ios-opt');o.length&&o[3].click();});
  document.querySelectorAll('textarea').forEach(t=>{if(!t.value&&!t.disabled)set(t,'A few honest words.');});});

try{
  await pg.goto('http://localhost:5599/',{waitUntil:'networkidle'}); await pg.waitForSelector('.landing-hero',{timeout:20000});
  await T('Begin').click(); await settle(200);
  await pg.locator('.consent-check input').check().catch(()=>{}); await T('I agree').click(); await settle(200);
  await pg.locator('.flow-body input').first().fill('Maya'); await T('Continue').click(); await settle(200);
  // pre-survey loop — capture the imagine page + the CIP page
  let imagine=false, cip=false;
  for(let i=0;i<16;i++){
    if(!(await pg.locator('.flow-progress').count()) && !(await pg.locator('.sv-imagine').count()))break;
    if(!imagine && await pg.locator('.sv-imagine').count()){ imagine=true; await shot('01-imagine'); }
    if(!cip && await pg.locator('.sv-scale-text',{hasText:"I can't commit to a career"}).count()){ cip=true; await shot('02-cip'); }
    await autofill(); await pg.waitForTimeout(60);
    const btn=(await T('Done').count())?T('Done'):(await T('Continue').count()?T('Continue'):T('Begin'));
    if(!(await btn.count())||await btn.isDisabled())break; await safe(btn); await pg.waitForTimeout(80);
  }
  await safe(T('Continue')); await settle(200); // pause A→B
  // phase B
  await pg.locator('.pb-composer textarea').fill('I like turning messy data into clear stories.').catch(()=>{});
  await safe(pg.locator('.pb-composer .send')); await pg.waitForTimeout(500);
  await safe(pg.locator('.rec-card').first()); await pg.waitForTimeout(300);
  await pg.evaluate(()=>document.querySelectorAll('.pb-lock-sheet .sv-scale').forEach(s=>{const p=s.querySelectorAll('.sv-pt');p.length&&p[p.length-1].click();}));
  await pg.locator('.pb-lock-sheet input').first().fill('Data analyst').catch(()=>{}); await settle(200);
  await safe(T('Step into this future')); await pg.waitForTimeout(400);
  await safe(T('Begin')); await settle(300); // pause B→C
  // phase C chat → finish
  await pg.waitForSelector('.chat-app',{timeout:8000}).catch(()=>{});
  await pg.locator('.composer textarea').fill('What surprised you most?').catch(()=>{});
  await safe(pg.locator('.composer .send')); await pg.waitForTimeout(500);
  await safe(T('Finish')); await pg.waitForTimeout(300);
  await safe(T('Finish & reflect')); await pg.waitForTimeout(300);
  await settle(200);
  if(await pg.locator('.pause-actions').count()){ await shot('03-pause-cpost'); await safe(T('Continue')); await settle(300); }
  // post-survey
  for(let i=0;i<16;i++){
    if(!(await pg.locator('.flow-progress').count()))break;
    if(i===0) await shot('04-postsurvey');
    if(await pg.locator('.sv-scale-text',{hasText:"I can't commit to a career"}).count() && !(await pg.locator('.ff-cip-post').count())) await shot('05-cip-post');
    await autofill(); await pg.waitForTimeout(60);
    const btn=(await T('Done').count())?T('Done'):T('Continue'); if(!(await btn.count())||await btn.isDisabled())break; await safe(btn); await pg.waitForTimeout(80);
  }
  await settle(300);
  await shot('06-explore-hub');
  // finish to closure
  await safe(T('Finish')); await safe(T('End')); await safe(T('Done')); await pg.waitForTimeout(400);
  await settle(300); await shot('07-closure');
}catch(e){ console.error('walk err', e.message); await shot('99-errorstate'); }
console.log('PAGE ERRORS:', errs.length); errs.slice(0,6).forEach(e=>console.log('  -',e));
await b.close(); srv.close();
