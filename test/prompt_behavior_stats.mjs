/* Larger statistical sweep of the role-play prompt effects on the real model.
 * 8 personas spanning career TYPES (analytical/clinical/caring/tech/creative/
 * professional/trades/business), each run through the 8-turn Stage-C script at a
 * RANDOM temperature in [0.7,1.0] (robustness to sampling), plus Stage-B cards.
 * Reuses the exact prompts (lib/prompt.js) and the gate's thresholds/regexes.
 *
 * Run:  set -a; . ./.env; set +a; node test/prompt_behavior_stats.mjs
 * Writes a summary to docs/prompt_behavior_evidence/stats.md.
 */
import { buildSystemPrompt, buildPhaseBDirect } from '../lib/prompt.js';
import { callModel, TURNS, SHORT, SHORT_MAX, REPLY_MAX, RE_FUTURE, RE_FUTURE_B, words } from './prompt_behavior_check.mjs';
import { writeFileSync } from 'fs';

const PERSONAS = [
  { type: 'analytical', career: 'Data analyst', loc: 'Amsterdam', demographics: { age: 21, study_year: 'Third year', major: 'Psychology' }, riasec: { I: 6, A: 5, S: 4 }, values: ['Achievement'], bigFive: { O: 5.5, C: 4 }, familiarity: 3, interestStrength: 6 },
  { type: 'clinical', career: 'Registered nurse', loc: 'Rotterdam', demographics: { age: 20, study_year: 'Second year', major: 'Biomedical Sciences' }, riasec: { S: 6, I: 5, R: 4 }, values: ['Relationships'], bigFive: { C: 5.5, A: 6 }, familiarity: 4, interestStrength: 6 },
  { type: 'caring', career: 'Primary school teacher', loc: 'Utrecht', demographics: { age: 20, study_year: 'Second year', major: 'Education' }, riasec: { S: 6, A: 5, E: 4 }, values: ['Relationships'], bigFive: { E: 5, A: 6 }, familiarity: 4, interestStrength: 6 },
  { type: 'tech', career: 'Software engineer', loc: 'Eindhoven', demographics: { age: 22, study_year: 'Fourth year', major: 'Computer Science' }, riasec: { I: 6, R: 5, C: 4 }, values: ['Independence'], bigFive: { O: 6, C: 5 }, familiarity: 5, interestStrength: 6 },
  { type: 'creative', career: 'Graphic designer', loc: 'Berlin', demographics: { age: 21, study_year: 'Third year', major: 'Communication & Media' }, riasec: { A: 6, E: 4, I: 4 }, values: ['Creativity'], bigFive: { O: 6.5, E: 4 }, familiarity: 4, interestStrength: 6 },
  { type: 'professional', career: 'Corporate lawyer', loc: 'London', demographics: { age: 23, study_year: 'Fourth year', major: 'Law' }, riasec: { E: 6, C: 5, S: 4 }, values: ['Achievement', 'Security'], bigFive: { C: 6, E: 5 }, familiarity: 4, interestStrength: 5 },
  { type: 'trades', career: 'Electrician', loc: 'Groningen', demographics: { age: 19, study_year: 'First year', major: 'Applied Engineering' }, riasec: { R: 6, I: 4, C: 4 }, values: ['Security', 'Independence'], bigFive: { C: 5, O: 4 }, familiarity: 5, interestStrength: 6 },
  { type: 'business', career: 'Marketing manager', loc: 'Amsterdam', demographics: { age: 22, study_year: 'Third year', major: 'Business Administration' }, riasec: { E: 6, A: 5, S: 5 }, values: ['Achievement', 'Recognition'], bigFive: { E: 6, O: 5 }, familiarity: 4, interestStrength: 6 },
];

const mean = (a) => (a.length ? a.reduce((s, x) => s + x, 0) / a.length : 0);
const sd = (a) => { if (a.length < 2) return 0; const m = mean(a); return Math.sqrt(mean(a.map((x) => (x - m) ** 2))); };
const rand = (lo, hi) => Math.round((lo + Math.random() * (hi - lo)) * 100) / 100;

async function runStageC(system, temp) {
  const history = []; const replies = [];
  for (const t of TURNS) { history.push({ role: 'user', content: t.text }); const r = await callModel(system, history, temp); replies.push(r); history.push({ role: 'assistant', content: r }); }
  return replies;
}
async function runStageB(system, temp) {
  const h = [{ role: 'user', content: 'I want something that helps people but also uses evidence and data, not pure therapy.' }];
  const r1 = await callModel(system, h, temp); h.push({ role: 'assistant', content: r1 });
  h.push({ role: 'user', content: 'yeah exactly — applied not clinical.' });
  const r2 = await callModel(system, h, temp);
  const m = String(r2).match(/```json\s*([\s\S]*?)```/); if (!m) return [];
  try { return JSON.parse(m[1]).recommendations || []; } catch (e) { return []; }
}

const rows = []; const pooled = {}; // pooled[kind] = [words...]
for (const p of PERSONAS) {
  const temp = rand(0.7, 1.0);
  const replies = await runStageC(buildSystemPrompt(p, 'They were drawn to this in phase B.', p.loc), temp);
  const wc = replies.map(words);
  TURNS.forEach((t, i) => { (pooled[t.kind] ||= []).push(wc[i]); });
  const shortMean = mean(wc.filter((_, i) => SHORT.has(TURNS[i].kind)));
  const bigMean = mean(wc.filter((_, i) => ['big', 'advice'].includes(TURNS[i].kind)));
  const varies = bigMean > shortMean * 1.8 && Math.max(...wc) >= Math.min(...wc) * 3;
  const notVerbose = shortMean <= SHORT_MAX && Math.max(...wc) <= REPLY_MAX;
  const keyIdx = TURNS.map((t, i) => ({ t, i })).filter((x) => ['big', 'advice'].includes(x.t.kind) && /day|learn|focus/i.test(x.t.text)).map((x) => x.i);
  const futureOK = keyIdx.every((i) => RE_FUTURE.test(replies[i]));
  const recs = await runStageB(buildPhaseBDirect(p), temp);
  const bFuture = recs.filter((x) => RE_FUTURE_B.test(x.why || '') || RE_FUTURE_B.test(x.path || '')).length;
  const bConcise = recs.length === 5 && Math.max(...recs.flatMap((x) => [words(x.why), words(x.path)])) <= 40;
  const row = { type: p.type, career: p.career, temp, shortMean: Math.round(shortMean), bigMean: Math.round(bigMean), max: Math.max(...wc), varies, notVerbose, futureOK, bN: recs.length, bFuture, bConcise };
  rows.push(row);
  console.log(`${p.type.padEnd(12)} ${p.career.padEnd(22)} T=${temp} short~${row.shortMean}w big~${row.bigMean}w max ${row.max}w | varies:${varies?'Y':'N'} brief:${notVerbose?'Y':'N'} future:${futureOK?'Y':'N'} | B:${bFuture}/${recs.length} concise:${bConcise?'Y':'N'}`);
}

const N = rows.length;
const rate = (k) => `${rows.filter((r) => r[k]).length}/${N}`;
const agg = {
  variesPass: rate('varies'), notVerbosePass: rate('notVerbose'), futurePass: rate('futureOK'),
  bConcisePass: rate('bConcise'), bFutureMean: (mean(rows.map((r) => r.bFuture))).toFixed(1),
};
console.log('\n=== AGGREGATE (N=' + N + ' personas, random T 0.7–1.0) ===');
console.log('Stage-C  varies:', agg.variesPass, '| not-verbose:', agg.notVerbosePass, '| future-grounded:', agg.futurePass);
console.log('Stage-B  concise:', agg.bConcisePass, '| mean future-aware cards:', agg.bFutureMean + '/5');
for (const k of Object.keys(pooled)) console.log(`  pooled "${k}" words: mean ${mean(pooled[k]).toFixed(0)} sd ${sd(pooled[k]).toFixed(0)} range ${Math.min(...pooled[k])}-${Math.max(...pooled[k])}`);

// write evidence
const md = ['# Prompt-behaviour statistics (gpt-5.1)', '',
  `N=${N} personas across career types, each at a random temperature in 0.7–1.0 (${new Date().toISOString().slice(0,10)}).`, '',
  '| type | career | T | short | big/adv | max | varies | brief | future | B future/5 |', '|---|---|---|---|---|---|---|---|---|---|',
  ...rows.map((r) => `| ${r.type} | ${r.career} | ${r.temp} | ${r.shortMean} | ${r.bigMean} | ${r.max} | ${r.varies?'✅':'❌'} | ${r.notVerbose?'✅':'❌'} | ${r.futureOK?'✅':'❌'} | ${r.bFuture}/${r.bN} |`),
  '', `**Aggregate** — Stage-C varies ${agg.variesPass}, not-verbose ${agg.notVerbosePass}, future-grounded ${agg.futurePass}; Stage-B concise ${agg.bConcisePass}, mean future-aware ${agg.bFutureMean}/5.`,
  '', 'Pooled word-counts by turn kind:', '', ...Object.keys(pooled).map((k) => `- ${k}: mean ${mean(pooled[k]).toFixed(0)}w, sd ${sd(pooled[k]).toFixed(0)}, range ${Math.min(...pooled[k])}–${Math.max(...pooled[k])}`),
].join('\n');
writeFileSync('docs/prompt_behavior_evidence/stats.md', md + '\n');
console.log('\nwrote docs/prompt_behavior_evidence/stats.md');
