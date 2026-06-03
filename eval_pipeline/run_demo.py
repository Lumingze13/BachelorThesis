"""
run_demo.py — one-command demo entry point.

Usage:
    python -m eval_pipeline.run_demo
    python eval_pipeline/run_demo.py

Runs the full evaluation pipeline offline on synthetic data,
writes out/report.html, out/results.csv, and figures.
"""

import os
import sys
import time
from pathlib import Path

# Ensure package root is on path when run as script
_HERE = Path(__file__).parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from eval_pipeline.synth import SyntheticGenerator, save_synthetic_sessions
from eval_pipeline.loader import load_session
from eval_pipeline.llm_client import FakeLLM
from eval_pipeline.embedder import get_default_embedder
from eval_pipeline.pipeline import run_pipeline, aggregate_metrics
from eval_pipeline.report import (
    fig_predicted_vs_actual,
    fig_bland_altman,
    fig_depth_ablation,
    fig_delta_vs_level,
    fig_observable_vs_felt,
    save_results_csv,
    build_report_html,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

N_PARTICIPANTS = 24
SEED = 42
N_RUNS = 5
DEPTHS = ["D0", "D1", "D2", "D3"]
PROMPT_STRUCTURES = ["structured", "narrative", "interview"]

BASE_DIR = Path(__file__).parent
OUT_DIR = BASE_DIR / "out"
FIG_DIR = OUT_DIR / "figures"
DATA_DIR = BASE_DIR / "data" / "raw"

for d in [OUT_DIR, FIG_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def main():
    t0 = time.time()
    print("=" * 60)
    print("Future-Self Career Chatbot — Evaluation Pipeline Demo")
    print("OFFLINE mode: using synthetic data + FakeLLM")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Generate synthetic sessions
    # ------------------------------------------------------------------
    print(f"\n[1/6] Generating {N_PARTICIPANTS} synthetic sessions (seed={SEED})...")
    gen = SyntheticGenerator(n=N_PARTICIPANTS, seed=SEED)
    raw_sessions = gen.generate()

    # Save under out/ (demo artifacts) — NEVER under data/raw, which is
    # reserved for real session exports. Cleared fresh on each run.
    import shutil as _shutil
    _synth_dir = OUT_DIR / "synth_sessions"
    # best-effort clean; the workspace mount may block deletes, so ignore errors
    # (filenames are deterministic for fixed seed/N, so files simply overwrite).
    _shutil.rmtree(_synth_dir, ignore_errors=True)
    _synth_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = save_synthetic_sessions(raw_sessions, str(_synth_dir))
    print(f"      Saved {len(saved_paths)} files to {_synth_dir}/")

    # ------------------------------------------------------------------
    # 2. Load sessions (re-read from disk to test loader, re-attach latent)
    # ------------------------------------------------------------------
    print("\n[2/6] Loading sessions via canonical loader...")
    # Use saved_paths (in generation order) so zip alignment with raw_sessions is exact.
    loaded_sessions = []
    for path, raw_sess in zip(saved_paths, raw_sessions):
        sess = load_session(path)
        # Re-attach latent truth for FakeLLM — stripped from saved JSON by design.
        sess["_latent"] = raw_sess.get("_latent", {})
        loaded_sessions.append(sess)
    print(f"      Loaded {len(loaded_sessions)} sessions")

    # ------------------------------------------------------------------
    # 3. Run pipeline
    # ------------------------------------------------------------------
    print(f"\n[3/6] Running pipeline ({N_PARTICIPANTS} participants × "
          f"{len(DEPTHS)} depths × {len(PROMPT_STRUCTURES)} structures × {N_RUNS} runs)...")
    total_runs = N_PARTICIPANTS * len(DEPTHS) * len(PROMPT_STRUCTURES) * N_RUNS
    print(f"      Total calls: {total_runs}")

    llm = FakeLLM(seed=SEED)
    embedder = get_default_embedder()

    results = run_pipeline(
        sessions=loaded_sessions,
        depths=DEPTHS,
        prompt_structures=PROMPT_STRUCTURES,
        llm=llm,
        embedder=embedder,
        n_runs=N_RUNS,
        verbose=True,
    )
    print(f"      Pipeline complete: {len(results)} result records")

    # ------------------------------------------------------------------
    # 4. Aggregate metrics
    # ------------------------------------------------------------------
    print("\n[4/6] Aggregating metrics with bootstrap CIs...")
    agg = aggregate_metrics(results)
    print(f"      {len(agg)} (depth × structure × outcome) metric sets")

    # ------------------------------------------------------------------
    # 5. Produce figures + CSV
    # ------------------------------------------------------------------
    print("\n[5/6] Producing figures and results CSV...")

    fig_paths = {}
    fig_paths["scatter"] = fig_predicted_vs_actual(results, str(FIG_DIR))
    fig_paths["ba"] = fig_bland_altman(results, str(FIG_DIR))
    fig_paths["depth_ablation"] = fig_depth_ablation(agg, str(FIG_DIR))
    fig_paths["delta_vs_level"] = fig_delta_vs_level(agg, str(FIG_DIR))
    fig_paths["observable_vs_felt"] = fig_observable_vs_felt(agg, str(FIG_DIR))

    csv_path = str(OUT_DIR / "results.csv")
    save_results_csv(agg, csv_path)
    print(f"      Saved results.csv → {csv_path}")

    # ------------------------------------------------------------------
    # 6. Build HTML report
    # ------------------------------------------------------------------
    print("\n[6/6] Building HTML report...")
    report_path = str(OUT_DIR / "report.html")
    build_report_html(
        figure_paths=fig_paths,
        aggregated_metrics=agg,
        out_path=report_path,
        n_participants=N_PARTICIPANTS,
        depths=DEPTHS,
        prompt_structures=PROMPT_STRUCTURES,
        n_runs=N_RUNS,
    )
    print(f"      Saved report.html → {report_path}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"DEMO COMPLETE in {elapsed:.1f}s")
    print(f"  report.html → {report_path}")
    print(f"  results.csv → {csv_path}")
    print(f"  figures     → {FIG_DIR}/")
    print()

    # Print headline metrics table (D0 vs D2, structured, spearman)
    print("HEADLINE METRICS (structured prompt, Spearman ρ):")
    print(f"{'Depth':<6} {'Outcome':<18} {'Spearman ρ':>12} {'Δ-corr':>10} {'Inter-run SD':>13}")
    print("-" * 65)
    from eval_pipeline.schema import OUTCOMES as OUT_CFG, DEPTH_LABELS
    for depth in ["D0", "D2", "D3"]:
        for outcome_name in ["continuity", "vividness", "closeness", "manip_checks"]:
            key = (depth, "structured", outcome_name)
            m = agg.get(key, {})
            rho = m.get("spearman", (float("nan"),))
            dc = m.get("delta_corr", (float("nan"),))
            irsd = m.get("interrun_sd_mean", float("nan"))
            rho_s = f"{rho[0]:.3f}" if rho and len(rho) >= 1 and rho[0] == rho[0] else "  n/a"
            dc_s = f"{dc[0]:.3f}" if dc and len(dc) >= 1 and dc[0] == dc[0] else "  n/a"
            irsd_s = f"{irsd:.3f}" if irsd == irsd else "  n/a"
            print(f"{depth:<6} {outcome_name:<18} {rho_s:>12} {dc_s:>10} {irsd_s:>13}")
        print()

    print("NOTE: Results are based on SYNTHETIC data with planted latent truth.")
    print("      Real-data results will differ. See report.html for full details.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
