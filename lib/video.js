/*
 * video.js — optional "day in the life" pre-chat stimulus (Google Veo via the
 * Gemini API). At the Phase B→C handoff, once the participant has chosen a
 * career, this renders three short first-person POV clips — morning, afternoon,
 * evening of one ordinary weekday ten years on — personalised to the career,
 * location, and what they told the recommendation guide.
 *
 * OFF by default. Active only when VIDEO_ENABLED is truthy AND a Gemini key is
 * set, so the fielded study is unchanged until the team turns it on. Generation
 * is fresh per participant (a research/cost decision — every session renders new
 * clips), runs server-side (the Veo file URIs need the API key), and is streamed
 * to the browser through a proxy endpoint. @google/genai is imported lazily so a
 * missing package or key never blocks the rest of the app.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { buildDayInLifeScenePrompt } from './prompt.js';

const GEMINI_API_KEY = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY || '';
const VIDEO_ENABLED = /^(1|true|yes|on)$/i.test(process.env.VIDEO_ENABLED || '');
const VEO_MODEL = process.env.VEO_MODEL || 'veo-3.1-fast-generate-preview';
const VEO_ASPECT = process.env.VEO_ASPECT || '16:9';
const VEO_RESOLUTION = process.env.VEO_RESOLUTION || '720p';
const VEO_DURATION = process.env.VEO_DURATION || '8';
const POLL_MS = Number(process.env.VEO_POLL_MS || 10000);
const TIMEOUT_MS = Number(process.env.VEO_TIMEOUT_MS || 6 * 60 * 1000);
const JOB_TTL_MS = Number(process.env.VEO_JOB_TTL_MS || 30 * 60 * 1000);

const SEGMENTS = ['morning', 'afternoon', 'evening'];
const TMP_DIR = path.join(os.tmpdir(), 'thesis-day-in-life');

/** Feature is live only when explicitly enabled AND a key is present. */
export function dayInLifeEnabled() {
  return VIDEO_ENABLED && Boolean(GEMINI_API_KEY);
}

const jobs = new Map(); // jobId -> { status, segments:[{label, ready, error, file}], error, createdAt }

export function getJob(id) {
  return jobs.get(id) || null;
}

/** Absolute path of a ready clip, or null. Used by the streaming proxy. */
export function segmentFile(jobId, label) {
  const job = jobs.get(jobId);
  if (!job) return null;
  const seg = job.segments.find((s) => s.label === label);
  return seg && seg.ready && seg.file && fs.existsSync(seg.file) ? seg.file : null;
}

/** A serialisable snapshot for the polling endpoint. */
export function jobStatus(jobId) {
  const job = jobs.get(jobId);
  if (!job) return null;
  return {
    status: job.status, // 'pending' | 'ready' | 'error'
    error: job.error || null,
    segments: job.segments.map((s) => ({
      label: s.label,
      ready: s.ready,
      error: s.error || null,
      url: s.ready ? `/api/day-in-life/${jobId}/${s.label}` : null,
    })),
  };
}

// Wrap a written scene in fixed shot/style scaffolding for the video model.
function wrapPrompt(scene) {
  return `First-person POV, the camera is the person's own eyes — we never see their face, only what they see (their hands, the desk, the street, screens, people across from them). ${scene} Cinematic, natural light, shallow depth of field, photorealistic, gentle handheld motion. Ambient sound only — no voiceover, no music with lyrics, no on-screen text or captions.`;
}

// Deterministic fallback if Claude's scene JSON can't be parsed.
function fallbackScenes(career, place) {
  const where = place && !/pinned down/.test(place) ? ` in ${place}` : '';
  return {
    morning: `Waking up${where} on an ordinary weekday, light through the curtains, reaching for a coffee, glancing at the day ahead working as a ${career}.`,
    afternoon: `Mid-afternoon, deep in the work of a ${career}${where} — the screen, the desk, a colleague leaning in to talk something through.`,
    evening: `Evening, the work done, heading home${where} as the light goes golden, settling in for the night.`,
  };
}

function parseScenes(raw, career, place) {
  try {
    const m = (raw || '').match(/\{[\s\S]*\}/);
    if (m) {
      const obj = JSON.parse(m[0]);
      if (obj && obj.morning && obj.afternoon && obj.evening) return obj;
    }
  } catch { /* fall through */ }
  return fallbackScenes(career, place);
}

/**
 * Kick off a fresh generation. `complete(system, messages)` is the server's LLM
 * caller (Claude), passed in so we don't duplicate the client. Returns a jobId
 * immediately; the work runs in the background.
 */
export function startDayInLifeJob({ profileData = {}, phaseBNotes = '', location = '', complete }) {
  const jobId = crypto.randomUUID();
  const job = {
    status: 'pending',
    error: null,
    segments: SEGMENTS.map((label) => ({ label, ready: false, error: null, file: null, op: null })),
    createdAt: Date.now(),
  };
  jobs.set(jobId, job);
  runJob(jobId, { profileData, phaseBNotes, location, complete }).catch((err) => {
    job.status = 'error';
    job.error = err?.message || String(err);
    console.error('day-in-life job failed:', job.error);
  });
  // Best-effort cleanup so /tmp and the Map don't grow unbounded.
  setTimeout(() => cleanup(jobId), JOB_TTL_MS).unref?.();
  return jobId;
}

async function runJob(jobId, { profileData, phaseBNotes, location, complete }) {
  const job = jobs.get(jobId);
  if (!job) return;
  const career = (profileData.career || 'this career').toString().trim();
  const place = (location || '').toString().trim();

  // 1. Lazy-load the SDK so a missing package never crashes the server.
  let GoogleGenAI;
  try {
    ({ GoogleGenAI } = await import('@google/genai'));
  } catch (e) {
    job.status = 'error';
    job.error = 'Video SDK not installed (@google/genai).';
    return;
  }
  const ai = new GoogleGenAI({ apiKey: GEMINI_API_KEY });

  // 2. Ask Claude for three POV scenes (fall back to templates on any failure).
  let scenes = fallbackScenes(career, place);
  try {
    const { system, user } = buildDayInLifeScenePrompt(profileData, phaseBNotes, location);
    const raw = await complete(system, [{ role: 'user', content: user }]);
    scenes = parseScenes(raw, career, place);
  } catch (e) {
    console.warn('day-in-life scene prompt failed, using fallback:', e?.message || e);
  }

  await fs.promises.mkdir(TMP_DIR, { recursive: true });

  // 3. Start all three Veo generations in parallel, then poll each to completion.
  await Promise.all(job.segments.map(async (seg) => {
    try {
      let operation = await ai.models.generateVideos({
        model: VEO_MODEL,
        prompt: wrapPrompt(scenes[seg.label]),
        config: {
          aspectRatio: VEO_ASPECT,
          resolution: VEO_RESOLUTION,
          durationSeconds: Number(VEO_DURATION), // API requires a number, not a string
          numberOfVideos: 1,
        },
      });
      const deadline = Date.now() + TIMEOUT_MS;
      while (!operation.done) {
        if (Date.now() > deadline) throw new Error('generation timed out');
        await new Promise((r) => setTimeout(r, POLL_MS));
        operation = await ai.operations.getVideosOperation({ operation });
      }
      const video = operation.response?.generatedVideos?.[0]?.video;
      if (!video) throw new Error('no video in response');
      const file = path.join(TMP_DIR, `${jobId}-${seg.label}.mp4`);
      await ai.files.download({ file, downloadPath: file });
      seg.file = file;
      seg.ready = true;
    } catch (e) {
      seg.error = e?.message || String(e);
      console.warn(`day-in-life ${seg.label} failed:`, seg.error);
    }
  }));

  // 4. Ready if at least one clip rendered; otherwise error.
  job.status = job.segments.some((s) => s.ready) ? 'ready' : 'error';
  if (job.status === 'error' && !job.error) job.error = 'All clips failed to render.';
}

function cleanup(jobId) {
  const job = jobs.get(jobId);
  if (job) {
    for (const s of job.segments) {
      if (s.file) { try { fs.unlinkSync(s.file); } catch { /* gone already */ } }
    }
  }
  jobs.delete(jobId);
}
