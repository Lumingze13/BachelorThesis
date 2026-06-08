/*
 * lib/silicon_cohort.js — Pass A of the silicon-cohort method validation.
 *
 * For each real cohort profile: a participant LLM (default Opus) plays the
 * student, (1) self-reports the PRE questionnaire, (2) optionally does a short
 * Phase-B career chat with the guide bot, (3) does the Phase-C future-self chat
 * with the SAME Sonnet bot the humans used, (4) self-reports the POST
 * questionnaire. The result is a canonical `study` JSON — identical shape to a
 * real session — so Pass B (eval_pipeline judge, default Sonnet) reads it
 * unchanged. Participant model != judge model = no trivial self-agreement.
 *
 * LLMs are injectable, so the whole assembly is unit-tested offline with stubs.
 */

import fs from 'node:fs';
import path from 'node:path';

import {
  runConversation, makeClaudeLlm, PHASE_B_NUDGE, PHASE_C_NUDGE,
} from './simulator.js';
import {
  buildPhaseBPrompt, buildSystemPrompt, buildSimulatorPersonaPrompt,
  buildSelfReportPrompt, selfReportItemIds,
} from './prompt.js';
import { loadCohort } from './personas.js';

function parseJsonObject(text) {
  const m = (text || '').match(/\{[\s\S]*\}/);
  if (!m) return {};
  try { return JSON.parse(m[0]); } catch { return {}; }
}

/** The persona answers one questionnaire phase; returns {item_id: int 1-7}. */
export async function elicitSelfReport(profileData, transcript, phase, llm) {
  const { system, user } = buildSelfReportPrompt(profileData, { phase, transcript });
  const raw = await llm(system, [{ role: 'user', content: user }]);
  const obj = parseJsonObject(raw);
  const out = {};
  for (const id of selfReportItemIds(phase)) {
    const v = Math.round(Number(obj[id]));
    out[id] = Number.isFinite(v) ? Math.max(1, Math.min(7, v)) : 4;
  }
  return out;
}

/** Run one persona end-to-end → canonical `study` JSON. */
export async function runOnePersona({
  profileData, participantLlm, botLlm, phaseBTurns = 2, phaseCTurns = 5,
}) {
  const participantSystem = buildSimulatorPersonaPrompt(profileData);

  // (1) PRE self-report (before any chat)
  const pre = await elicitSelfReport(profileData, [], 'pre', participantLlm);

  // (2) optional short Phase-B career chat (gives D2 "own words")
  let transcriptB = [];
  if (phaseBTurns > 0) {
    transcriptB = await runConversation({
      botSystem: buildPhaseBPrompt(profileData),
      participantSystem, openerNudge: PHASE_B_NUDGE, turns: phaseBTurns,
      botLlm, participantLlm,
    });
  }

  // (3) Phase-C future-self chat (the same bot humans used)
  const transcriptC = await runConversation({
    botSystem: buildSystemPrompt(profileData, ''),
    participantSystem, openerNudge: PHASE_C_NUDGE, turns: phaseCTurns,
    botLlm, participantLlm,
  });

  // (4) POST self-report (after the chat)
  const post = await elicitSelfReport(profileData, transcriptC, 'post', participantLlm);

  const turnCount = transcriptC.filter((m) => m.role === 'user').length;
  return {
    meta: { condition: 'main', version: 'silicon-1', completedAt: new Date().toISOString(), synthetic: true },
    profile: { name: profileData._pid, color: '#b5552f' },
    preSurvey: {
      age: profileData.demographics?.age,
      gender: profileData.demographics?.gender,
      year: profileData.year,
      ...pre,
    },
    scores: { bigFive: profileData.bigFive, riasec: profileData.riasec, values: profileData.values },
    phaseB: {
      career: profileData.career,
      familiarity: profileData.familiarity,
      interestStrength: profileData.interestStrength,
      transcript: transcriptB,
    },
    phaseC: { transcript: transcriptC, durationSec: phaseCTurns * 60, turnCount },
    postSurvey: { ...post, interview: false },
  };
}

/** Run the whole cohort (Pass A) and write one <pid>.json per persona. */
export async function runCohortToDir({
  csvPath, n, phaseBTurns = 2, phaseCTurns = 5,
  participantModel = 'claude-opus-4-6', botModel = 'claude-sonnet-4-6',
  outDir, llms, onProgress,
}) {
  const personas = loadCohort(csvPath, { limit: n });
  const participantLlm = llms?.participant || makeClaudeLlm(participantModel);
  const botLlm = llms?.bot || makeClaudeLlm(botModel);
  fs.mkdirSync(outDir, { recursive: true });

  const paths = [];
  for (let i = 0; i < personas.length; i++) {
    const study = await runOnePersona({
      profileData: personas[i], participantLlm, botLlm, phaseBTurns, phaseCTurns,
    });
    const p = path.join(outDir, `${personas[i]._pid}.json`);
    fs.writeFileSync(p, JSON.stringify(study));
    paths.push(p);
    onProgress?.(i + 1, personas.length, personas[i]._pid);
  }
  return paths;
}
