# Silicon cohort — simulated participants for method validation

Run the RQ pipeline end-to-end on **simulated** participants seeded from real
open-data profiles. This validates the method and shows the expected shape of the
result **before** human data exists.

> **What this is / isn't.** Inputs (Big Five + RIASEC + demographics) are REAL
> (open dataset). The bot usage and the questionnaire answers are AI-generated.
> So "agreement" here is judge ↔ **simulated** participant = pipeline
> reproducibility / sensitivity under design choices — **method validation, not
> human ground truth.** The headline RQ claim still needs human data.
>
> Anti-circularity: the **participant** model (Opus) ≠ the **judge** model
> (Sonnet), so high agreement can't be one model trivially predicting itself.

## Two passes
- **Pass A** (`run_silicon_cohort.mjs`, Node): each real profile → participant
  LLM (Opus) plays the student → self-reports PRE → short Phase-B career chat →
  Phase-C future-self chat with the **same Sonnet bot the humans used** →
  self-reports POST → one canonical `study` JSON (identical shape to a real
  session).
- **Pass B** (spawns `eval_pipeline.run_eval --use-real`, Python): the judge
  (Sonnet) predicts each participant's ratings from the transcript across persona
  depth (D0–D3) × prompt structure → MAE / Spearman / QWK / ICC / inter-run SD.

## Run it
0. Cohort already selected → `data/cohort_100.csv` (see `data/README.md`).
   Re-select with `python3 scripts/select_cohort.py --in data/riasec.csv --out data/cohort_100.csv --n 100`.
1. Put a fresh `ANTHROPIC_API_KEY` in `.env` (**rotate the previously-exposed one first**).
2. **Eyeball one persona** before spending:
   ```
   node run_silicon_cohort.mjs --n 1 --phase-c-turns 5 --skip-eval
   ```
   Open the produced `eval_pipeline/out/silicon_*/sessions/PID001.json` — check the
   conversation reads like a real student and the self-reports look sane.
3. **Small real run** (recommended starting point):
   ```
   node run_silicon_cohort.mjs --n 30 --depths D0,D2,D3 --k 3
   ```
4. Full report opens at `eval_pipeline/out/silicon_<ts>/eval/report.html`.

### Flags
`--csv` (default `data/cohort_100.csv`) · `--n` participants · `--phase-b-turns`
(default 2) · `--phase-c-turns` (default 5) · `--participant-model` (default
`claude-opus-4-6`) · `--bot-model` (default `claude-sonnet-4-6`) · `--depths`
(default `D0,D1,D2,D3`) · `--structures` (default `structured`) · `--k`
(runs/participant, default 5) · `--skip-eval` (Pass A only).

> If your account uses a different Opus id, pass it via `--participant-model`.

## Cost — read before scaling
The **judge (Pass B) dominates**: ≈ `n × 11 items × k × |depths| × |structures|`
Sonnet calls. n=100, k=5, depths=4 → ~88k calls. Start small.
Pass A adds, per participant: ≈ `phaseB + phaseC + 2` **Opus** calls (Opus is the
priciest model) + a handful of Sonnet bot calls. Keep `--n`, `--k`, and `--depths`
modest for demos (e.g. n=30, k=3, depths D0,D2,D3).

## Honest framing for the report
- Simulated participants → **method validation / dry-run**, not a finding.
- Inputs real (open data), behaviour + ratings AI-generated.
- LLMs follow requested traits only partially (and can be stereotyped) → surface-
  plausible, not validated human behaviour.
- Single judge model (Sonnet); persuasiveness not collected by the app.
