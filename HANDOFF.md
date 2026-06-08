# HANDOFF — for Claude Code to continue

Thesis = BSc Business Analytics (UvA). RQ: **how do design choices in an LLM-based
evaluation pipeline (persona depth, prompt structure, judge model) affect its
agreement with human evaluation on IBM outcomes (continuity, vividness,
persuasiveness) for a 10-year career future-self chatbot.** Artifact = the
deployed chatbot + study platform + eval pipeline. Repo root: `~/Desktop/thesis`.

## ⏭️ RESUME HERE (the active task)
Run the **silicon-cohort method-validation** end-to-end with real models. Everything
is built and verified OFFLINE; only the real LLM run remains (it needs the API key,
which the previous assistant could not accept via chat).

1. Ensure a fresh `ANTHROPIC_API_KEY` is in `.env` (rotate the exposed ones first —
   see Security below). Judge defaults to `claude-sonnet-4-6`; participant defaults
   to `claude-opus-4-6`.
2. **Eyeball one persona** (cheap):
   ```
   node run_silicon_cohort.mjs --n 1 --phase-c-turns 5 --skip-eval
   ```
   Open `eval_pipeline/out/silicon_*/sessions/PID001.json` — check the Phase-C
   dialogue reads like a real student and the pre/post self-reports look sane.
   Tune `lib/prompt.js` (`buildSimulatorPersonaPrompt` / `buildSelfReportPrompt`) if needed.
3. **Small real run** → report:
   ```
   node run_silicon_cohort.mjs --n 30 --depths D0,D2,D3 --k 3
   ```
   Report: `eval_pipeline/out/silicon_<ts>/eval/report.html`.
4. Then (optional) wire silicon runs + the `/results` page for the supervisor demo.

## The silicon-cohort method (design is LOCKED with the user)
Real open-data profiles → AI "silicon participants" → run the RQ pipeline on them.
Honest framing: **inputs are real, behaviour + ratings are AI-generated → this is
method validation / a dry-run (LLM↔LLM agreement), NOT human ground truth.** The
headline RQ still needs human data (Thy Le's study + Kaehl, or the team's own
collection).
- **Pass A** (`run_silicon_cohort.mjs` → `lib/silicon_cohort.js`, Node): each
  profile → participant LLM (**Opus**) plays the student → self-reports PRE → short
  Phase-B career chat → Phase-C future-self chat with the **same Sonnet bot the
  humans used** → self-reports POST → canonical `study` JSON (same shape as a real
  session).
- **Pass B** (spawns `python -m eval_pipeline.run_eval --sessions-dir <dir>
  --use-real`): judge (**Sonnet**) predicts ratings from the transcript across
  depth × structure → MAE / Spearman / QWK / ICC / inter-run SD.
- **Anti-circularity:** participant model (Opus) ≠ judge model (Sonnet). D3 is the
  deliberate leakage probe; D0–D2 must never see outcome items (guard in
  `eval_pipeline/persona.py`).

## Files added/changed THIS session
Silicon cohort (the active thread):
- `scripts/select_cohort.py` — filters the RIASEC dataset to our frame (undergrad
  age + business/econ/analytics major + quality screen) and ranks by a
  Business-Analytics RIASEC archetype. **Already run** → `data/cohort_100.csv`
  (100 personas from the real n=145,828 dataset). Raw `data/riasec.csv` is
  git-ignored. `data/README.md` documents the source.
- `lib/personas.js` — `loadCohort(csv)` → `profileData`; assigns career (major +
  top-RIASEC), values, year, familiarity/interest (the fields the dataset lacks).
- `lib/prompt.js` — added `buildSimulatorPersonaPrompt` (silicon participant voice)
  and `buildSelfReportPrompt` / `selfReportItemIds` (persona fills the
  questionnaires; item ids match the loader).
- `lib/simulator.js` — `runConversation({botSystem, participantSystem, ...})`
  generic bot↔bot loop; `makeClaudeLlm(model)`; `PHASE_B_NUDGE`/`PHASE_C_NUDGE`.
  (`runSimulatedConversation` kept as a back-compat wrapper for /results.)
- `lib/silicon_cohort.js` — `runOnePersona`, `elicitSelfReport`, `runCohortToDir`.
- `run_silicon_cohort.mjs` — CLI orchestrator (Pass A → Pass B). Flags in
  `SILICON_COHORT.md`.
- `test/silicon_cohort.test.mjs` — offline test (stub LLMs).
- `SILICON_COHORT.md` — full run guide + cost + honest framing.

Earlier this session (built + offline-verified, **NOT deployed**):
- Read-only supervisor results page `/results` (gated by new `RESULTS_TOKEN`):
  `lib/results_routes.js`, `results/index.html`, `results/login.html`, mounted in
  `server.js`. Tabs: Overview / RQ results / Real-vs-simulated / Browse sessions
  (anonymized). Plan in `RESULTS_PAGE_PLAN.md`.
- Bot↔bot "simulations" feature: `simulations` table (`db/schema.sql`),
  `lib/simulator.js`, admin "Simulations" tab (`admin/index.html`), admin endpoints
  (`lib/admin_routes.js`). Launch from `/admin` once deployed.
- `demo_results/` — an ILLUSTRATIVE synthetic eval report (N=80 toy generator,
  FakeLLM) + `hero_agreement_by_depth.png` + `PRESENTER_NOTES.md` for a supervisor
  demo. (Clearly labeled simulated; not human, not the open-data cohort.)

## Verified offline (no API calls)
- `node --check` clean on all changed JS.
- `cd /tmp && node ~/Desktop/thesis/test/simulator.test.mjs` and
  `.../test/silicon_cohort.test.mjs` → PASS (stub LLMs; run from a dir without a
  `.env` if you want to avoid loading real creds).
- Python judge loader reads a produced silicon `study` JSON and computes
  outcomes_pre/post.
- Full dry-run on the real cohort (n=5, stub LLMs + FakeLLM judge) produced
  `report.html` — plumbing works on real profiles. (`ConstantInputWarning` there is
  expected: stub text → undefined correlations.)
- The eval pipeline's own offline synthetic demo runs:
  `python -m eval_pipeline.run_eval --synthetic --n 80 --depths D0,D1,D2,D3
  --structures structured --n-runs 5 --out-dir <dir> --summary-json <dir>/summary.json`.

## NOT done / TODO
- **The real Opus+Sonnet silicon run** (the resume step above). Never executed.
- Deploy the `/results` page + simulations: `git push` (Railway, Node+Python via
  nixpacks) and set `RESULTS_TOKEN` in Railway env. Schema auto-migrates on boot.
- `eval_pipeline/report.py` still prints a "DEMONSTRATION ON SYNTHETIC DATA" banner
  even for db/real and silicon runs — relabel by source/model/N (lines ~496–612).
- Per-session predictions aren't exposed by the eval API (only aggregate `summary`)
  — add a `predictions.json` output + `eval_runs.predictions` column for exact
  per-session real-vs-predicted tables on `/results`.
- Cohort gender skew 71F/29M (property of the dataset) — optional gender
  stratification in `scripts/select_cohort.py`.
- Cost: the **judge dominates** (~ n × 11 items × k × |depths| Sonnet calls). Keep
  n/k/depths modest. Opus (participant) is priciest per call but fewer calls.

## Security (carry forward — important)
- Treat as COMPROMISED and rotate: the original `ANTHROPIC_API_KEY`, the Postgres
  password in `DATABASE_URL`, `ADMIN_TOKEN` (all leaked in an earlier paste), and
  **two ANTHROPIC keys the user pasted into chat** in this session.
- Never commit secrets. Keys live only in `.env` (git-ignored) / Railway env.
- `/results` serves only de-identified, name-stripped data and is read-only.

## Reference docs already in the repo
`SILICON_COHORT.md`, `RESULTS_PAGE_PLAN.md`, `STUDY_PLATFORM_SPEC.md`,
`RESEARCH_PLAN_eval_pipeline.md`, `README.md`, `data/README.md`,
`demo_results/PRESENTER_NOTES.md`.
