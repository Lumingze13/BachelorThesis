"""
run_eval.py — parameterized evaluation entry point used by the dashboard.

Two data sources:
  --synthetic [--n N --seed S]   offline synthetic sessions (deterministic FakeLLM gradient)
  --sessions-dir DIR             real session JSONs (exported from the DB by Node)

Writes <out-dir>/report.html (self-contained), results.csv, figures/, and the
--summary-json file (headline metrics). Prints SUMMARY_JSON_PATH:<path> on success.

Node (lib/eval_runner.js) owns all DB I/O; this script never touches Postgres.
"""

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

# Ensure package root is importable when run via `python -m eval_pipeline.run_eval`
_HERE = Path(__file__).parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from eval_pipeline.synth import SyntheticGenerator, save_synthetic_sessions
from eval_pipeline.loader import load_session, load_all_sessions
from eval_pipeline.llm_client import get_llm
from eval_pipeline.embedder import get_default_embedder
from eval_pipeline.pipeline import run_pipeline, aggregate_metrics
from eval_pipeline.report import (
    fig_predicted_vs_actual, fig_bland_altman, fig_depth_ablation,
    fig_delta_vs_level, fig_observable_vs_felt, save_results_csv, build_report_html,
)
from eval_pipeline.schema import OUTCOMES, DEPTH_LABELS


def _num(x):
    try:
        f = float(x)
        return None if not math.isfinite(f) else round(f, 4)
    except Exception:
        return None


def _first(t):
    return _num(t[0]) if isinstance(t, (list, tuple)) and t else _num(t)


def build_summary(agg, depths, structures, n_part, source, use_real):
    headline = []
    for depth in depths:
        for ps in structures:
            for outcome in OUTCOMES.keys():
                m = agg.get((depth, ps, outcome))
                if not m:
                    continue
                headline.append({
                    "depth": depth, "prompt_structure": ps, "outcome": outcome,
                    "spearman": _first(m.get("spearman")),
                    "qwk": _first(m.get("qwk")),
                    "icc21": _first(m.get("icc21")),
                    "mae": _first(m.get("mae")),
                    "n_sessions": m.get("n_sessions"),
                    "interrun_sd": _num(m.get("interrun_sd_mean")),
                })
    return {
        "source": source, "use_real": use_real, "n_participants": n_part,
        "depths": depths, "prompt_structures": structures, "headline": headline,
    }


def _safe_fig(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        print(f"[run_eval] figure {getattr(fn, '__name__', fn)} skipped: {e}", flush=True)
        return None


def _fallback_report(agg, depths, structures, n_part, out_path):
    rows = []
    for depth in depths:
        for ps in structures:
            for outcome in OUTCOMES.keys():
                m = agg.get((depth, ps, outcome))
                if not m:
                    continue
                sp = m.get("spearman", (float("nan"),))[0]
                rows.append(f"<tr><td>{depth}</td><td>{DEPTH_LABELS.get(depth,'')}</td>"
                            f"<td>{ps}</td><td>{outcome}</td>"
                            f"<td>{'' if sp != sp else f'{sp:.3f}'}</td>"
                            f"<td>{m.get('n_sessions','')}</td></tr>")
    html = ("<!doctype html><meta charset='utf-8'><title>Eval report</title>"
            "<style>body{font-family:system-ui;margin:30px}table{border-collapse:collapse}"
            "td,th{border:1px solid #ccc;padding:6px 10px}</style>"
            f"<h1>Evaluation report (fallback)</h1><p>{n_part} participants.</p>"
            "<table><tr><th>Depth</th><th>Label</th><th>Structure</th><th>Outcome</th>"
            "<th>Spearman ρ</th><th>n</th></tr>" + "".join(rows) + "</table>")
    Path(out_path).write_text(html, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--summary-json", required=True)
    ap.add_argument("--depths", default="D0,D2,D3")
    ap.add_argument("--structures", default="structured")
    ap.add_argument("--n-runs", type=int, default=5)
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--sessions-dir", default=None)
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--use-real", action="store_true")
    args = ap.parse_args()

    depths = [d.strip() for d in args.depths.split(",") if d.strip()]
    structures = [s.strip() for s in args.structures.split(",") if s.strip()]

    out_dir = Path(args.out_dir)
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    # --- Load sessions ---
    if args.sessions_dir:
        sessions = load_all_sessions(args.sessions_dir)
        if not sessions:
            print(f"[run_eval] ERROR: no sessions in {args.sessions_dir}", file=sys.stderr)
            return 2
        source = "db"
        print(f"[run_eval] loaded {len(sessions)} DB session(s)")
    else:
        gen = SyntheticGenerator(n=args.n, seed=args.seed)
        raw = gen.generate()
        synth_dir = out_dir / "synth_sessions"
        shutil.rmtree(synth_dir, ignore_errors=True)
        synth_dir.mkdir(parents=True, exist_ok=True)
        paths = save_synthetic_sessions(raw, str(synth_dir))
        sessions = []
        for p, r in zip(paths, raw):
            s = load_session(p)
            s["_latent"] = r.get("_latent", {})  # FakeLLM needs planted truth
            sessions.append(s)
        source = "synthetic"
        print(f"[run_eval] generated {len(sessions)} synthetic session(s)")

    llm = get_llm(use_real=args.use_real, seed=args.seed)
    embedder = get_default_embedder()

    results = run_pipeline(
        sessions=sessions, depths=depths, prompt_structures=structures,
        llm=llm, embedder=embedder, n_runs=args.n_runs, verbose=True,
    )
    agg = aggregate_metrics(results)

    # --- Figures + report (resilient to arbitrary depth/structure subsets) ---
    fig_paths = {}
    for key, fn, arg in [
        ("scatter", fig_predicted_vs_actual, results),
        ("ba", fig_bland_altman, results),
        ("depth_ablation", fig_depth_ablation, agg),
        ("delta_vs_level", fig_delta_vs_level, agg),
        ("observable_vs_felt", fig_observable_vs_felt, agg),
    ]:
        p = _safe_fig(fn, arg, str(fig_dir))
        if p:
            fig_paths[key] = p

    try:
        save_results_csv(agg, str(out_dir / "results.csv"))
    except Exception as e:
        print(f"[run_eval] results.csv skipped: {e}", flush=True)

    report_path = out_dir / "report.html"
    try:
        build_report_html(
            figure_paths=fig_paths, aggregated_metrics=agg, out_path=str(report_path),
            n_participants=len(sessions), depths=depths,
            prompt_structures=structures, n_runs=args.n_runs,
        )
    except Exception as e:
        print(f"[run_eval] build_report_html failed ({e}); writing fallback report", flush=True)
        _fallback_report(agg, depths, structures, len(sessions), str(report_path))

    summary = build_summary(agg, depths, structures, len(sessions), source, args.use_real)
    sp = Path(args.summary_json)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("SUMMARY_JSON_PATH:" + str(sp.resolve()), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
