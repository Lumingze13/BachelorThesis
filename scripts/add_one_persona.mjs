/*
 * One-off: generate a single silicon persona by cohort index and write it into
 * an existing sessions dir (used to top a partial Pass A up to N).
 *   node scripts/add_one_persona.mjs <index1based> <sessionsDir>
 */
import '../lib/env.js';
import fs from 'node:fs';
import path from 'node:path';
import { loadCohort } from '../lib/personas.js';
import { runOnePersona } from '../lib/silicon_cohort.js';
import { makeClaudeLlm } from '../lib/simulator.js';

const idx = parseInt(process.argv[2], 10);          // 1-based persona number
const outDir = process.argv[3];
if (!idx || !outDir) { console.error('usage: add_one_persona.mjs <index1based> <sessionsDir>'); process.exit(1); }

const p = loadCohort('data/cohort_100.csv', { limit: idx })[idx - 1];
const dest = path.join(outDir, p._pid + '.json');
console.log('Generating ' + p._pid + ' — ' + p.career + ' (participant=opus-4-6, bot=sonnet-4-6)…');

const t0 = Date.now();
const study = await runOnePersona({
  profileData: p,
  participantLlm: makeClaudeLlm('claude-opus-4-6'),
  botLlm: makeClaudeLlm('claude-sonnet-4-6'),
  phaseBTurns: 2, phaseCTurns: 5,
});
fs.writeFileSync(dest, JSON.stringify(study));
console.log('Wrote ' + dest + ' in ' + ((Date.now() - t0) / 1000).toFixed(0) + 's — career ' + study.phaseB.career + ', phaseC turns ' + study.phaseC.turnCount);
