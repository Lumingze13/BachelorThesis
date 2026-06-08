/*
 * Offline test for the silicon-cohort Pass A (no network, no DB, no API key).
 * Stub LLMs are injected; we assert the produced study JSON has the canonical
 * shape (so the Python judge reads it unchanged) and that personas load + get a
 * career. A separate bash step then runs the real Python loader on the output.
 *
 * Run from a dir WITHOUT .env so dotenv (override:true) can't pull real creds:
 *   cd /tmp && node <repo>/test/silicon_cohort.test.mjs
 */

import assert from 'node:assert/strict';
import fs from 'node:fs';
import { loadCohort, assignCareer } from '../lib/personas.js';
import { runOnePersona } from '../lib/silicon_cohort.js';
import { selfReportItemIds } from '../lib/prompt.js';

// --- tiny cohort fixture (selector output schema) ---------------------------
const FIX = '/tmp/cohort_fixture.csv';
fs.writeFileSync(FIX,
  'pid,age,gender,country,education,major,riasec_R,riasec_I,riasec_A,riasec_S,riasec_E,riasec_C,big5_O,big5_C,big5_E,big5_A,big5_N,fit_rank,fit_score\n' +
  'PID001,19,Female,MY,High school,accounting,1.75,3.62,2.0,3.25,3.38,3.12,3.0,3.33,4.0,2.0,2.67,1,-2.1\n' +
  'PID002,21,Male,US,University degree,Economics,1.5,4.0,1.6,3.1,3.3,3.5,4.0,3.7,2.3,3.0,2.5,2,-2.2\n' +
  'PID003,20,Female,NL,High school,marketing,2.0,3.2,2.8,3.4,3.6,3.0,3.6,4.0,4.2,3.2,2.0,3,-2.3\n');

// --- personas load + career assignment --------------------------------------
const personas = loadCohort(FIX);
assert.equal(personas.length, 3, 'loads 3 personas');
assert.ok(typeof personas[0].career === 'string' && personas[0].career.length, 'career assigned');
assert.equal(personas[0].demographics.age, 19);
assert.equal(typeof personas[0].bigFive.O, 'number');
assert.equal(assignCareer({ R: 1, I: 1, A: 1, S: 1, E: 5, C: 1 }, '', 'x'),
  // top RIASEC = E -> one of the Enterprising careers
  assignCareer({ R: 1, I: 1, A: 1, S: 1, E: 5, C: 1 }, '', 'x'), 'career deterministic');

// --- stub LLMs --------------------------------------------------------------
const allIds = [...selfReportItemIds('pre'), ...selfReportItemIds('post')];
let convoCalls = 0, surveyCalls = 0;
const participantLlm = async (system, _msgs) => {
  if (system.includes('filling in a short survey')) {
    surveyCalls += 1;
    return 'Sure, here you go:\n' + JSON.stringify(Object.fromEntries(allIds.map((k) => [k, 5])));
  }
  convoCalls += 1;
  return `participant line ${convoCalls}`;
};
const botLlm = async () => 'future-self line';

// --- run one persona end-to-end --------------------------------------------
const study = await runOnePersona({
  profileData: personas[0], participantLlm, botLlm, phaseBTurns: 1, phaseCTurns: 2,
});

// canonical shape the Python judge/loader expects
assert.equal(study.meta.condition, 'main');
assert.equal(study.profile.name, 'PID001');
assert.equal(study.preSurvey.fscs_similar, 5, 'pre item present');
assert.equal(study.preSurvey.ios_pre, 5, 'pre ios present');
assert.ok(!('mc_style' in study.preSurvey), 'no manip checks in PRE');
assert.equal(study.postSurvey.fscs_similar_post, 5, 'post item present');
assert.equal(study.postSurvey.ios_post, 5, 'post ios present');
assert.equal(study.postSurvey.mc_style, 5, 'manip check in POST');
assert.equal(study.phaseB.transcript.length, 2, 'phaseB: opening + 1 participant turn');
assert.equal(study.phaseC.transcript.length, 4, 'phaseC: 2 exchanges');
assert.equal(study.phaseC.turnCount, 2, 'phaseC turnCount = participant turns');
assert.ok(typeof study.scores.bigFive.O === 'number', 'scores carried');
assert.ok(study.phaseB.career && study.phaseB.career.length, 'career in phaseB');
// 2 survey calls (pre+post) + 1 phaseB participant turn + 2 phaseC participant turns = 3 convo
assert.equal(surveyCalls, 2, '2 self-report calls (pre + post)');
assert.equal(convoCalls, 3, '3 participant conversation turns');

fs.writeFileSync('/tmp/silicon_sample.json', JSON.stringify(study, null, 2));
console.log(`PASS — personas=${personas.length}; study JSON shape OK; survey=${surveyCalls} convo=${convoCalls}`);
console.log(`career[0]=${personas[0].career} | wrote /tmp/silicon_sample.json`);
