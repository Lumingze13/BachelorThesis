# Supervisor demo — illustrative simulation

**One-line disclaimer to say out loud (and it's on every figure):**
> "These numbers are an **illustration on simulated participants** — they show
> what the evaluation pipeline produces and the pattern we *expect* once we
> collect human data. They are **not** human findings yet."

This is exactly the DSR "mock-up + evaluation MVP" stage the first-draft
guidelines ask for (Modeling & Design → present mock-up; Evaluation → design MVP).

---

## The 3-beat story
1. **The artifact runs end-to-end.** Study platform (chatbot + Postgres + admin)
   → `/results` dashboard → eval pipeline. Here it's exercised on **N=80
   simulated participants** with planted ground truth.
2. **Expected pattern — agreement rises with persona depth.** As the LLM
   evaluator gets a richer persona (D0 demographics → D1 +psychometrics → D2 +the
   participant's own words), its agreement with the participant's own ratings
   climbs. The transcript-**observable** family (manipulation checks) is easiest.
3. **Our anti-circularity guard works.** D3 deliberately leaks pre-outcome
   scores into the persona; agreement on the *felt* outcomes jumps to ρ≈0.82 —
   the pipeline **detects** that inflation, which is the validity check that keeps
   us honest. We do **not** report D3 as a "good" setting.

## The numbers behind the hero chart (simulated, N=80)
Spearman ρ (judge ↔ participant) by persona depth:

| Outcome | D0 | D1 | D2 | D3 (leakage) |
|---|---|---|---|---|
| Continuity (felt) | 0.18 | 0.45 | 0.45 | 0.82 |
| Vividness (felt) | 0.01 | 0.35 | 0.41 | 0.81 |
| Closeness (felt) | −0.06 | 0.28 | 0.40 | 0.84 |
| Manip. checks (observable) | 0.13 | 0.22 | **0.98** | −0.16 |

MAE shrinks alongside (e.g. manip-checks D2 MAE = 0.18 on a 1–7 scale).

## What to show
- **`hero_agreement_by_depth.png`** — the slide. The whole story in one chart.
- **`eval_report_simulated.html`** — open in a browser for the deep-dive
  (Predicted-vs-Actual scatter, Bland–Altman, depth ablation, Δ-vs-level,
  observable-vs-felt) + the metric glossary + the limitations section.
- Individual `fig_*.png` — drop into slides as needed.

## What's still needed (say this proactively)
- **Human ground truth** for the real agreement claim: Thy Le's study + Kaehl,
  and/or our own session collection. The dashboards fill with real numbers then.
- This simulated run is **method validation + a dry-run** of the full analysis,
  so when human data arrives the pipeline and metrics are already locked.
- Single judge model here (Sonnet in production; offline stub for this demo);
  persuasiveness is not collected by the app yet.

## If a supervisor asks "is this real?"
Answer plainly: *no — simulated, to validate the method and show the expected
shape of the result; the human data is the next step.* That honesty is a
strength, not a weakness, at this stage.
