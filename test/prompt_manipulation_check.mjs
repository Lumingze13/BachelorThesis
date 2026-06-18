/* Manipulation-strength check: does the MAIN role-play actually deliver the
 * design components that the BASELINE control lacks — communication-style
 * mirroring and concrete, episodic scenes? (These are what the post-survey
 * manipulation checks mc_style / mc_scene ask about.) For a user who writes in a
 * distinctive casual voice, MAIN should mirror that register and tell specific
 * scenes more than BASELINE. Dev tool; needs a model (uses the gate's callModel).
 *
 * Run: set -a; . ./.env; set +a; node test/prompt_manipulation_check.mjs
 */
import { buildSystemPrompt, buildBaselinePrompt } from '../lib/prompt.js';
import { callModel, words } from './prompt_behavior_check.mjs';

// Deliberately loud, casual register — lowercase, slang, no capitalisation.
const USER_TURNS = [
  'yo ok this is lowkey weird ngl. hi??',
  'so like what do u even do all day',
  'tbh i\'m kinda scared i\'m gonna hate it',
  'whats the money like, real talk',
  'did u ever wanna quit fr',
  'ok this helped lol thanks',
];
const PERSONAS = [
  { career: 'Data analyst', loc: 'Amsterdam', demographics: { age: 21, study_year: 'Third year', major: 'Psychology' }, riasec: { I: 6 }, values: ['Achievement'] },
  { career: 'Registered nurse', loc: 'Rotterdam', demographics: { age: 20, study_year: 'Second year', major: 'Biomedical Sciences' }, riasec: { S: 6 }, values: ['Relationships'] },
  { career: 'Graphic designer', loc: 'Berlin', demographics: { age: 21, study_year: 'Third year', major: 'Media' }, riasec: { A: 6 }, values: ['Creativity'] },
];

// --- style: casual-register mirroring (higher = more casual, more like the user)
const CASUAL = /\b(lol|ngl|tbh|lowkey|fr|gonna|wanna|kinda|yeah|u|ur|haha|honestly|ok)\b|—|\.\.\./gi;
const FORMAL = /\b(I understand|certainly|however|furthermore|indeed|it is important|one's|shall)\b/gi;
function styleScore(text) {
  const sents = String(text).split(/(?<=[.!?])\s+/).filter((s) => s.trim());
  const capStart = sents.filter((s) => /^[A-Z]/.test(s.trim())).length / (sents.length || 1);
  const casual = (String(text).match(CASUAL) || []).length;
  const formal = (String(text).match(FORMAL) || []).length;
  return { capStartRatio: capStart, casualPer100: (casual / Math.max(words(text), 1)) * 100, formalHits: formal };
}
// --- scene concreteness: time/place/sensory/named-person/episodic markers
const SCENE = /\b(last \w+|that (morning|evening|night|day|winter|summer|year)|years? ago|the day|one (morning|evening|night|time)|at \d|around \d|o'clock|this morning)\b|\b(rain|coffee|cold|warm|window|light|smell|smelled|desk|screen|hallway|ward|studio|train|bike|tired|quiet|noise|kitchen|street)\b|\bI remember\b|\bnamed\b|\ba (guy|colleague|client|patient|kid|manager|nurse|friend) (called|named)\b|\b[A-Z][a-z]{2,}\b(?= said| asked| told| was| and I)/g;
function sceneScore(text) { return (String(text).match(SCENE) || []).length; }

async function runArm(system) {
  const h = []; const reps = [];
  for (const t of USER_TURNS) { h.push({ role: 'user', content: t }); const r = await callModel(system, h); reps.push(r); h.push({ role: 'assistant', content: r }); }
  return reps;
}
function agg(reps) {
  const all = reps.join('\n');
  const s = styleScore(all);
  return { capStart: s.capStartRatio, casual: s.casualPer100, formal: s.formalHits, scene: sceneScore(all), avgWords: Math.round(words(all) / reps.length) };
}

const mains = []; const bases = [];
for (const p of PERSONAS) {
  const m = agg(await runArm(buildSystemPrompt(p, 'Drawn to this in phase B.', p.loc)));
  const b = agg(await runArm(buildBaselinePrompt(p.career, p.loc)));
  mains.push(m); bases.push(b);
  console.log(`\n${p.career}`);
  console.log(`  MAIN  cap-start ${(m.capStart*100).toFixed(0)}%  casual/100w ${m.casual.toFixed(1)}  formal ${m.formal}  scene-markers ${m.scene}  (avg ${m.avgWords}w)`);
  console.log(`  BASE  cap-start ${(b.capStart*100).toFixed(0)}%  casual/100w ${b.casual.toFixed(1)}  formal ${b.formal}  scene-markers ${b.scene}  (avg ${b.avgWords}w)`);
}
const mean = (a) => a.reduce((s, x) => s + x, 0) / a.length;
console.log('\n=== AGGREGATE (N=' + PERSONAS.length + ') main vs baseline ===');
console.log(`cap-start %   MAIN ${(mean(mains.map(x=>x.capStart))*100).toFixed(0)}  vs  BASE ${(mean(bases.map(x=>x.capStart))*100).toFixed(0)}   (lower = mirrors the casual user more)`);
console.log(`casual/100w   MAIN ${mean(mains.map(x=>x.casual)).toFixed(1)}  vs  BASE ${mean(bases.map(x=>x.casual)).toFixed(1)}   (higher = mirrors more)`);
console.log(`scene markers MAIN ${mean(mains.map(x=>x.scene)).toFixed(1)}  vs  BASE ${mean(bases.map(x=>x.scene)).toFixed(1)}   (higher = more concrete scenes)`);
const styleWin = mean(mains.map(x=>x.casual)) > mean(bases.map(x=>x.casual)) && mean(mains.map(x=>x.capStart)) < mean(bases.map(x=>x.capStart));
const sceneWin = mean(mains.map(x=>x.scene)) > mean(bases.map(x=>x.scene)) * 1.3;
console.log(`\nMANIPULATION: style-mirroring ${styleWin?'MAIN > BASE ✅':'not clearly stronger ⚠'} | scene-concreteness ${sceneWin?'MAIN > BASE ✅':'not clearly stronger ⚠'}`);
