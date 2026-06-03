/*
 * lib/eval_runner.js — launches eval_pipeline runs and records them in eval_runs.
 *
 * Node owns all DB I/O: for a "db" run it exports the stored sessions to a temp
 * dir of <sessionId>.json files (the shape eval_pipeline's loader already reads)
 * and points Python at it — so the Python side needs no database driver. For a
 * "synthetic" run Python generates its own offline data. Results (summary +
 * self-contained HTML report) are written back to the eval_runs row.
 */

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { query } from './db.js';
import { exportStudies } from './sessions.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');
// Run artifacts (incl. exported sessions with PII) live OUTSIDE the static web
// root so they are never served. The report HTML is stored in the DB and served
// only through the gated admin endpoint.
const RUNS_DIR = path.join(os.tmpdir(), 'thesis_eval_runs');
const PYTHON_BIN = process.env.PYTHON_BIN || 'python3';

const DEPTHS = ['D0', 'D1', 'D2', 'D3'];
const STRUCTURES = ['structured', 'narrative', 'interview'];

function sanitizeConfig(input = {}) {
  const depths = Array.isArray(input.depths) && input.depths.length
    ? input.depths.filter((d) => DEPTHS.includes(d)) : ['D0', 'D2', 'D3'];
  const prompt_structures = Array.isArray(input.prompt_structures) && input.prompt_structures.length
    ? input.prompt_structures.filter((s) => STRUCTURES.includes(s)) : ['structured'];
  const n_runs = Math.min(Math.max(parseInt(input.n_runs, 10) || 5, 1), 20);
  const source = input.source === 'db' ? 'db' : 'synthetic';
  // The eval judge defaults to the real claude-sonnet-4-6 model. Synthetic runs
  // stay on the deterministic FakeLLM (their planted-truth gradient is the offline
  // self-test and is meaningless against a real judge), unless real is explicitly
  // requested. DB (real-participant) runs use the real judge by default.
  const use_real = input.use_real !== undefined
    ? Boolean(input.use_real)
    : source === 'db';
  const n_synth = Math.min(Math.max(parseInt(input.n_synth, 10) || 24, 4), 200);
  const model = (input.model || (use_real ? 'claude-sonnet-4-6' : 'fake')).toString().slice(0, 64);
  return { source, depths, prompt_structures, n_runs, use_real, n_synth, model };
}

export async function createRun(rawConfig) {
  const config = sanitizeConfig(rawConfig);
  const { rows } = await query(
    `INSERT INTO eval_runs (status, config) VALUES ('queued', $1) RETURNING *`,
    [JSON.stringify(config)]
  );
  const run = rows[0];
  // Fire-and-forget; status is tracked in the DB and polled by the dashboard.
  execute(run.id, config).catch(async (err) => {
    console.error('[eval] run', run.id, 'crashed:', err?.message || err);
    await query(`UPDATE eval_runs SET status='failed', error=$2 WHERE id=$1`,
      [run.id, String(err?.message || err).slice(0, 4000)]).catch(() => {});
  });
  return run;
}

async function execute(runId, config) {
  await query(`UPDATE eval_runs SET status='running' WHERE id=$1`, [runId]);

  const runDir = path.join(RUNS_DIR, runId);
  const outDir = path.join(runDir, 'out');
  const sessionsDir = path.join(runDir, 'sessions');
  fs.mkdirSync(outDir, { recursive: true });

  const args = ['-m', 'eval_pipeline.run_eval',
    '--out-dir', outDir,
    '--summary-json', path.join(outDir, 'summary.json'),
    '--depths', config.depths.join(','),
    '--structures', config.prompt_structures.join(','),
    '--n-runs', String(config.n_runs)];

  if (config.source === 'db') {
    fs.mkdirSync(sessionsDir, { recursive: true });
    const studies = await exportStudies({ status: 'completed' });
    if (!studies.length) throw new Error('No completed sessions in the database to evaluate.');
    for (const s of studies) {
      const id = s.meta?.sessionId || `s${Math.random().toString(36).slice(2)}`;
      fs.writeFileSync(path.join(sessionsDir, `${id}.json`), JSON.stringify(s));
    }
    args.push('--sessions-dir', sessionsDir);
  } else {
    args.push('--synthetic', '--n', String(config.n_synth), '--seed', '42');
  }
  if (config.use_real) args.push('--use-real');

  const summary = await runPython(args, runId);

  const reportPath = path.join(outDir, 'report.html');
  let reportHtml = null;
  try { reportHtml = fs.readFileSync(reportPath, 'utf8'); } catch { /* keep null */ }

  await query(
    `UPDATE eval_runs SET status='done', summary=$2, report_path=$3, report_html=$4 WHERE id=$1`,
    [runId, JSON.stringify(summary || {}), reportPath, reportHtml]
  );
}

function runPython(args, runId) {
  return new Promise((resolve, reject) => {
    const child = spawn(PYTHON_BIN, args, {
      cwd: ROOT,
      env: { ...process.env, PYTHONHASHSEED: '0', PYTHONPATH: ROOT },
    });
    let stderr = '';
    let stdout = '';
    child.stdout.on('data', (d) => { stdout += d.toString(); });
    child.stderr.on('data', (d) => { stderr += d.toString(); });
    child.on('error', reject);
    child.on('close', (code) => {
      if (code !== 0) {
        return reject(new Error(`python exited ${code}: ${(stderr || stdout).slice(-1500)}`));
      }
      // Python writes summary to the --summary-json path; recover it from stdout marker too.
      const m = stdout.match(/SUMMARY_JSON_PATH:(.+)/);
      try {
        const p = m ? m[1].trim() : null;
        const summary = p && fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : {};
        resolve(summary);
      } catch (e) {
        resolve({});
      }
    });
  });
}

export async function listRuns(limit = 100) {
  const { rows } = await query(
    `SELECT id, created_at, status, config, summary, error FROM eval_runs
     ORDER BY created_at DESC LIMIT $1`, [limit]);
  return rows;
}

export async function getRun(id) {
  const { rows } = await query(`SELECT * FROM eval_runs WHERE id=$1`, [id]);
  return rows[0] || null;
}
