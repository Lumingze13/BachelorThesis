"""
Report generator — produces:
  - out/figures/*.png  (all plots)
  - out/results.csv
  - out/report.html   (single self-contained file with embedded figures)
"""

import os
import base64
import csv
import io
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

# Matplotlib backend must be non-interactive for server/CI use
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

from eval_pipeline.schema import OUTCOMES, DEPTH_LABELS


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

DEPTH_COLORS = {
    "D0": "#bdc9e1",
    "D1": "#74a9cf",
    "D2": "#0570b0",
    "D3": "#d7301f",  # red = leakage probe
}
OUTCOME_COLORS = {
    "continuity": "#2ca25f",
    "vividness": "#8856a7",
    "closeness": "#e6550d",
    "manip_checks": "#3182bd",
}


def _ci_str(ci_tuple) -> str:
    """Format a (val, lo, hi) CI tuple as 'val [lo, hi]'."""
    if ci_tuple is None or len(ci_tuple) != 3:
        return "n/a"
    v, lo, hi = ci_tuple
    if not np.isfinite(v):
        return "n/a"
    lo_s = f"{lo:.2f}" if np.isfinite(lo) else "?"
    hi_s = f"{hi:.2f}" if np.isfinite(hi) else "?"
    return f"{v:.2f} [{lo_s}, {hi_s}]"


# ---------------------------------------------------------------------------
# Figure 1: Predicted vs Actual scatter (per outcome, D2 only)
# ---------------------------------------------------------------------------

def fig_predicted_vs_actual(
    results: List[Dict[str, Any]],
    out_dir: str,
    depth: str = "D2",
    prompt_structure: str = "structured",
) -> str:
    """Scatter plot of predicted vs actual ratings per outcome family."""
    from collections import defaultdict
    import matplotlib.gridspec as gridspec

    outcome_names = [k for k in OUTCOMES if k != "persuasiveness"]
    fig, axes = plt.subplots(1, len(outcome_names), figsize=(4 * len(outcome_names), 4))
    if len(outcome_names) == 1:
        axes = [axes]

    filtered = [r for r in results if r["depth"] == depth and r["prompt_structure"] == prompt_structure]

    for ax, outcome_name in zip(axes, outcome_names):
        by_session = defaultdict(list)
        for r in filtered:
            pred = r["predicted_outcomes"].get(outcome_name)
            actual = r["actual_outcomes_post"].get(outcome_name)
            if pred is not None and actual is not None and np.isfinite(pred):
                by_session[r["session_id"]].append((pred, actual))

        if not by_session:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            ax.set_title(OUTCOMES[outcome_name]["label"])
            continue

        preds = np.array([np.mean([x[0] for x in v]) for v in by_session.values()])
        actuals = np.array([v[0][1] for v in by_session.values()])

        color = OUTCOME_COLORS.get(outcome_name, "steelblue")
        ax.scatter(actuals, preds, alpha=0.7, color=color, edgecolors="white", linewidths=0.5, s=60)
        lo, hi = 1, 7
        ax.plot([lo, hi], [lo, hi], "k--", alpha=0.4, linewidth=1)
        ax.set_xlim(lo - 0.3, hi + 0.3)
        ax.set_ylim(lo - 0.3, hi + 0.3)
        ax.set_xlabel("Actual (post)")
        ax.set_ylabel("Predicted")
        ax.set_title(OUTCOMES[outcome_name]["label"])
        ax.set_aspect("equal")

        if len(preds) >= 3:
            from scipy.stats import spearmanr
            r, _ = spearmanr(preds, actuals)
            ax.text(0.05, 0.93, f"ρ={r:.2f}", transform=ax.transAxes, fontsize=9, color="navy")

    fig.suptitle(f"Predicted vs Actual — {DEPTH_LABELS.get(depth, depth)} | {prompt_structure}", fontsize=11)
    plt.tight_layout()
    path = os.path.join(out_dir, "fig_scatter.png")
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Figure 2: Bland-Altman (per outcome, D2 structured)
# ---------------------------------------------------------------------------

def fig_bland_altman(
    results: List[Dict[str, Any]],
    out_dir: str,
    depth: str = "D2",
    prompt_structure: str = "structured",
) -> str:
    from collections import defaultdict

    outcome_names = [k for k in OUTCOMES if k != "persuasiveness"]
    fig, axes = plt.subplots(1, len(outcome_names), figsize=(4 * len(outcome_names), 4))
    if len(outcome_names) == 1:
        axes = [axes]

    filtered = [r for r in results if r["depth"] == depth and r["prompt_structure"] == prompt_structure]

    for ax, outcome_name in zip(axes, outcome_names):
        by_session = defaultdict(list)
        for r in filtered:
            pred = r["predicted_outcomes"].get(outcome_name)
            actual = r["actual_outcomes_post"].get(outcome_name)
            if pred is not None and actual is not None and np.isfinite(pred):
                by_session[r["session_id"]].append((pred, actual))

        if not by_session:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            ax.set_title(OUTCOMES[outcome_name]["label"])
            continue

        preds = np.array([np.mean([x[0] for x in v]) for v in by_session.values()])
        actuals = np.array([v[0][1] for v in by_session.values()])

        means = (preds + actuals) / 2
        diffs = preds - actuals
        bias = np.mean(diffs)
        sd = np.std(diffs, ddof=1) if len(diffs) > 1 else 0
        loa_lo = bias - 1.96 * sd
        loa_hi = bias + 1.96 * sd

        color = OUTCOME_COLORS.get(outcome_name, "steelblue")
        ax.scatter(means, diffs, alpha=0.7, color=color, edgecolors="white", linewidths=0.5, s=60)
        ax.axhline(bias, color="navy", linestyle="-", linewidth=1.5, label=f"Bias={bias:.2f}")
        ax.axhline(loa_lo, color="red", linestyle="--", linewidth=1, label=f"LoA [{loa_lo:.2f},{loa_hi:.2f}]")
        ax.axhline(loa_hi, color="red", linestyle="--", linewidth=1)
        ax.axhline(0, color="gray", linestyle=":", linewidth=0.8)
        ax.set_xlabel("Mean of predicted & actual")
        ax.set_ylabel("Predicted − Actual")
        ax.set_title(OUTCOMES[outcome_name]["label"])
        ax.legend(fontsize=7, loc="upper right")

    fig.suptitle(f"Bland-Altman — {DEPTH_LABELS.get(depth, depth)} | {prompt_structure}", fontsize=11)
    plt.tight_layout()
    path = os.path.join(out_dir, "fig_ba.png")
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Figure 3: Agreement by persona depth (ablation curve)
# ---------------------------------------------------------------------------

def fig_depth_ablation(
    aggregated_metrics: Dict[Tuple, Dict[str, Any]],
    out_dir: str,
    prompt_structure: str = "structured",
    metric_key: str = "spearman",
    metric_label: str = "Spearman ρ",
) -> str:
    outcome_names = [k for k in OUTCOMES if k != "persuasiveness"]
    depths = ["D0", "D1", "D2", "D3"]

    fig, ax = plt.subplots(figsize=(7, 4))

    for outcome_name in outcome_names:
        vals, los, his = [], [], []
        for depth in depths:
            key = (depth, prompt_structure, outcome_name)
            m = aggregated_metrics.get(key, {})
            ci = m.get(metric_key, (float("nan"),) * 3)
            vals.append(ci[0] if ci else float("nan"))
            los.append(ci[1] if ci else float("nan"))
            his.append(ci[2] if ci else float("nan"))

        color = OUTCOME_COLORS.get(outcome_name, "steelblue")
        x = range(len(depths))
        ax.plot(x, vals, marker="o", color=color, label=OUTCOMES[outcome_name]["label"], linewidth=2)
        # CI ribbon
        valid_mask = [np.isfinite(v) and np.isfinite(l) and np.isfinite(h)
                      for v, l, h in zip(vals, los, his)]
        xv = [i for i, m in enumerate(valid_mask) if m]
        lv = [los[i] for i in xv]
        hv = [his[i] for i in xv]
        if xv:
            ax.fill_between(xv, lv, hv, alpha=0.15, color=color)

    ax.set_xticks(range(len(depths)))
    ax.set_xticklabels([f"{d}\n({DEPTH_LABELS[d]})" for d in depths], fontsize=8)
    ax.set_ylabel(metric_label)
    ax.set_title(f"Agreement by Persona Depth — {metric_label} | {prompt_structure}")
    ax.axvline(2.5, color="red", linestyle="--", alpha=0.5, label="D3 = leakage probe")
    ax.legend(fontsize=8, loc="upper left")
    ax.set_ylim(-0.3, 1.05)

    plt.tight_layout()
    path = os.path.join(out_dir, "fig_depth_ablation.png")
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Figure 4: Δ-correlation vs level-correlation bar chart
# ---------------------------------------------------------------------------

def fig_delta_vs_level(
    aggregated_metrics: Dict[Tuple, Dict[str, Any]],
    out_dir: str,
    depth: str = "D2",
    prompt_structure: str = "structured",
) -> str:
    outcome_names = [k for k in OUTCOMES if k != "persuasiveness"]
    labels = [OUTCOMES[k]["label"] for k in outcome_names]

    level_vals = []
    delta_vals = []

    for outcome_name in outcome_names:
        key = (depth, prompt_structure, outcome_name)
        m = aggregated_metrics.get(key, {})
        level_ci = m.get("spearman", (float("nan"),) * 3)
        delta_ci = m.get("delta_corr", (float("nan"),) * 3)
        level_vals.append(level_ci[0] if level_ci else float("nan"))
        delta_vals.append(delta_ci[0] if delta_ci else float("nan"))

    x = np.arange(len(outcome_names))
    width = 0.35
    fig, ax = plt.subplots(figsize=(7, 4))

    bars1 = ax.bar(x - width / 2, level_vals, width, label="Level correlation (Spearman ρ)",
                   color="#2166ac", alpha=0.85)
    bars2 = ax.bar(x + width / 2, delta_vals, width, label="Δ-correlation",
                   color="#d1e5f0", edgecolor="#2166ac", alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right", fontsize=9)
    ax.set_ylabel("Spearman ρ")
    ax.set_title(f"Level vs Δ-correlation — {DEPTH_LABELS.get(depth, depth)} | {prompt_structure}")
    ax.legend(fontsize=9)
    ax.set_ylim(-0.3, 1.05)
    ax.axhline(0, color="gray", linewidth=0.8)

    plt.tight_layout()
    path = os.path.join(out_dir, "fig_delta_vs_level.png")
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Figure 5: Transcript-observable vs felt outcome gradient
# ---------------------------------------------------------------------------

def fig_observable_vs_felt(
    aggregated_metrics: Dict[Tuple, Dict[str, Any]],
    out_dir: str,
    prompt_structure: str = "structured",
    metric_key: str = "spearman",
    metric_label: str = "Spearman ρ",
) -> str:
    depths = ["D0", "D1", "D2"]  # exclude D3 leakage probe
    observable = ["manip_checks"]
    felt = ["continuity", "vividness", "closeness"]

    fig, axes = plt.subplots(1, len(depths), figsize=(4 * len(depths), 4), sharey=True)

    for ax, depth in zip(axes, depths):
        obs_vals = []
        felt_vals = []

        for outcome_name in observable:
            key = (depth, prompt_structure, outcome_name)
            m = aggregated_metrics.get(key, {})
            ci = m.get(metric_key, (float("nan"),) * 3)
            obs_vals.append(ci[0] if ci else float("nan"))

        for outcome_name in felt:
            key = (depth, prompt_structure, outcome_name)
            m = aggregated_metrics.get(key, {})
            ci = m.get(metric_key, (float("nan"),) * 3)
            felt_vals.append(ci[0] if ci else float("nan"))

        obs_mean = np.nanmean(obs_vals) if obs_vals else float("nan")
        felt_mean = np.nanmean(felt_vals) if felt_vals else float("nan")

        categories = ["Transcript-\nobservable\n(manip checks)", "Felt outcomes\n(cont/viv/close)"]
        values = [obs_mean, felt_mean]
        colors = ["#3182bd", "#9ecae1"]

        bars = ax.bar(categories, values, color=colors, edgecolor="white")
        ax.set_title(f"{depth}\n({DEPTH_LABELS[depth]})", fontsize=9)
        ax.set_ylim(-0.3, 1.05)
        ax.axhline(0, color="gray", linewidth=0.8)
        if ax == axes[0]:
            ax.set_ylabel(metric_label)
        for bar, val in zip(bars, values):
            if np.isfinite(val):
                ax.text(bar.get_x() + bar.get_width() / 2, val + 0.02,
                        f"{val:.2f}", ha="center", va="bottom", fontsize=9)

    fig.suptitle(f"Observable vs Felt Outcomes — {metric_label}", fontsize=11)
    plt.tight_layout()
    path = os.path.join(out_dir, "fig_observable_vs_felt.png")
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Save results CSV
# ---------------------------------------------------------------------------

def save_results_csv(
    aggregated_metrics: Dict[Tuple, Dict[str, Any]],
    out_path: str,
) -> None:
    rows = []
    for (depth, ps, outcome_name), m in sorted(aggregated_metrics.items()):
        row = {
            "depth": depth,
            "depth_label": DEPTH_LABELS.get(depth, depth),
            "prompt_structure": ps,
            "outcome": outcome_name,
            "n": m.get("n_sessions", m.get("n", "?")),
            "mae": _ci_str(m.get("mae")),
            "spearman_rho": _ci_str(m.get("spearman")),
            "qwk": _ci_str(m.get("qwk")),
            "icc21": _ci_str(m.get("icc21")),
            "exact_acc": _ci_str(m.get("exact_acc")),
            "adjacent_acc": _ci_str(m.get("adjacent_acc")),
            "ba_bias": f"{m.get('ba_bias', float('nan')):.3f}",
            "ba_loa_lo": f"{m.get('ba_loa', (float('nan'),float('nan')))[0]:.3f}",
            "ba_loa_hi": f"{m.get('ba_loa', (float('nan'),float('nan')))[1]:.3f}",
            "delta_corr": _ci_str(m.get("delta_corr")),
            "interrun_sd": f"{m.get('interrun_sd_mean', float('nan')):.3f}",
        }
        rows.append(row)

    if not rows:
        return

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# HTML report builder
# ---------------------------------------------------------------------------

def _img_to_b64(path: str) -> str:
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{data}"


def _metrics_table_html(
    aggregated_metrics: Dict[Tuple, Dict[str, Any]],
    depths: List[str],
    prompt_structure: str = "structured",
) -> str:
    outcome_names = [k for k in OUTCOMES if k != "persuasiveness"]
    rows_html = []

    for depth in depths:
        is_leakage = depth == "D3"
        row_class = "leakage" if is_leakage else ""
        label = DEPTH_LABELS.get(depth, depth)
        leakage_note = " ⚠ LEAKAGE PROBE" if is_leakage else ""

        for outcome_name in outcome_names:
            key = (depth, prompt_structure, outcome_name)
            m = aggregated_metrics.get(key, {})
            if not m:
                continue

            rows_html.append(
                f"<tr class='{row_class}'>"
                f"<td><b>{depth}</b>{leakage_note}</td>"
                f"<td>{label}</td>"
                f"<td>{OUTCOMES[outcome_name]['label']}</td>"
                f"<td>{'Yes' if OUTCOMES[outcome_name]['observable'] else 'No'}</td>"
                f"<td>{m.get('n_sessions', '?')}</td>"
                f"<td>{_ci_str(m.get('spearman'))}</td>"
                f"<td>{_ci_str(m.get('qwk'))}</td>"
                f"<td>{_ci_str(m.get('icc21'))}</td>"
                f"<td>{_ci_str(m.get('mae'))}</td>"
                f"<td>{_ci_str(m.get('adjacent_acc'))}</td>"
                f"<td>{_ci_str(m.get('delta_corr'))}</td>"
                f"<td>{m.get('interrun_sd_mean', float('nan')):.3f}</td>"
                f"</tr>"
            )

    header = (
        "<tr>"
        "<th>Depth</th><th>Depth Label</th><th>Outcome</th><th>Observable?</th>"
        "<th>N</th>"
        "<th>Spearman ρ [95% CI]</th>"
        "<th>QWK [95% CI]</th>"
        "<th>ICC(2,1) [95% CI]</th>"
        "<th>MAE [95% CI]</th>"
        "<th>Adjacent Acc [95% CI]</th>"
        "<th>Δ-corr [95% CI]</th>"
        "<th>Inter-run SD</th>"
        "</tr>"
    )
    return f"<table border='1' cellpadding='4' cellspacing='0'>{header}{''.join(rows_html)}</table>"


def build_report_html(
    figure_paths: Dict[str, str],
    aggregated_metrics: Dict[Tuple, Dict[str, Any]],
    out_path: str,
    n_participants: int = 0,
    depths: Optional[List[str]] = None,
    prompt_structures: Optional[List[str]] = None,
    n_runs: int = 5,
    source: str = "synthetic",
    use_real: bool = False,
    model: Optional[str] = None,
    run_label: Optional[str] = None,
) -> None:
    """Build a self-contained HTML report with embedded figures."""
    if depths is None:
        depths = ["D0", "D1", "D2", "D3"]
    if prompt_structures is None:
        prompt_structures = ["structured"]

    # --- Source-aware framing (so real / silicon runs are not mislabeled) -----
    is_real = (source == "db") or use_real
    judge_name = model or ("real LLM" if use_real else "FakeLLM")
    if run_label:
        banner_html = (
            f'<div class="banner banner-real">{run_label}<br>'
            f'N={n_participants} sessions · judge={judge_name}. Agreement = judge-predicted vs '
            f'self-reported ratings. Small N → descriptive / pilot only.</div>'
        )
    elif is_real:
        banner_html = (
            f'<div class="banner banner-real">EVALUATION ON STORED SESSIONS — N={n_participants}; '
            f'judge={judge_name}.<br>An independent LLM judge predicts each session\'s self-report '
            f'ratings from the transcript; the table shows predicted-vs-actual agreement. '
            f'Small N → descriptive / pilot only.</div>'
        )
    else:
        banner_html = (
            '<div class="banner">⚠️  DEMONSTRATION ON SYNTHETIC DATA — method/plumbing '
            'validation only.<br>Real session exports drop in unchanged: place app JSON exports in '
            '<code>eval_pipeline/data/raw/</code> and re-run. '
            f'Results below reflect N={n_participants} synthetic participants with planted latent truth.</div>'
        )
    subtitle = ("Real-session evaluation report." if is_real
                else "Offline demo report. Generated automatically by <code>python -m eval_pipeline.run_demo</code>.")
    data_limit = (
        f"<li><b>Source</b>: stored sessions (N={n_participants}); judge={judge_name}. "
        f"Agreement is judge-predicted vs self-report. If sessions are AI-generated (silicon cohort), "
        f"this is LLM↔LLM method validation, not human ground truth.</li>" if is_real else
        "<li><b>Synthetic data only</b>: All results shown here use synthetic sessions with planted "
        "latent truth. Real session exports have not been collected yet.</li>"
    )

    # Embed all figures as base64
    fig_tags = {}
    for name, path in figure_paths.items():
        if os.path.exists(path):
            fig_tags[name] = f"<img src='{_img_to_b64(path)}' style='max-width:100%; height:auto;'>"
        else:
            fig_tags[name] = f"<p><em>Figure not available: {name}</em></p>"

    table_html = _metrics_table_html(aggregated_metrics, depths)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Future-Self Career Chatbot — Evaluation Pipeline Report</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; color: #222; }}
  .banner {{ background: #fff3cd; border: 2px solid #ffc107; border-radius: 6px; padding: 14px 18px;
            font-size: 1.1em; font-weight: bold; margin-bottom: 24px; }}
  .banner-real {{ background: #e8f3ee; border-color: #3f9d6a; color: #1f5d46; }}
  h1 {{ color: #003366; }}
  h2 {{ color: #003366; border-bottom: 1px solid #ccc; padding-bottom: 4px; }}
  h3 {{ color: #0570b0; }}
  table {{ border-collapse: collapse; font-size: 0.82em; width: 100%; margin-bottom: 20px; }}
  th {{ background: #003366; color: white; padding: 6px 8px; text-align: left; }}
  td {{ padding: 4px 8px; }}
  tr:nth-child(even) {{ background: #f5f5f5; }}
  tr.leakage {{ background: #ffe0e0 !important; }}
  .fig-row {{ display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 24px; }}
  .fig-box {{ flex: 1 1 45%; min-width: 300px; border: 1px solid #ddd; border-radius: 4px; padding: 10px; }}
  .fig-box h3 {{ margin: 0 0 8px 0; font-size: 0.95em; color: #555; }}
  .metric-def {{ background: #f0f4f8; border-left: 4px solid #0570b0; padding: 8px 12px;
                  margin: 8px 0; font-size: 0.87em; }}
  .leakage-warn {{ background: #ffe0e0; border-left: 4px solid #d7301f; padding: 8px 12px; margin: 8px 0; }}
  .limitations {{ background: #f9f0ff; border-left: 4px solid #8856a7; padding: 8px 12px; margin: 8px 0; font-size: 0.88em; }}
</style>
</head>
<body>

{banner_html}

<h1>Future-Self Career Chatbot — Evaluation Pipeline</h1>
<p><em>BSc Thesis — {subtitle}</em></p>

<h2>1. Method Summary</h2>
<p>
Students completed a ~30-minute future-self career chatbot study: pre-survey → career selection →
role-play conversation with an LLM acting as their future self (phaseC) → post-survey.
</p>
<p>
This pipeline answers: <strong>Can an LLM persona/digital-twin, built from a participant's questionnaire,
reproduce that participant's post-chat self-report ratings — and how do design choices
(persona depth, prompt structure) affect agreement with human ratings?</strong>
</p>
<p>
<strong>Design:</strong> For each participant, we build a persona prompt at a given depth (D0–D2),
feed it the participant's actual phaseC transcript, and ask it to fill in the post-survey
battery <em>as that participant</em>. Each Likert item is elicited via
<strong>SSR (Semantic Similarity Rating)</strong>: the persona generates a free-text response;
that response is embedded; cosine similarity to one anchor statement per scale point is
computed; softmax → expected value (continuous rating) and mode (discrete).
Agreement between predicted and actual post ratings is then quantified.
</p>
<p>
We ablate across:
<ul>
  <li><b>Persona depth</b>: D0 (demographics) → D1 (+psychometrics+career) → D2 (+own words)</li>
  <li><b>Prompt structure</b>: structured / narrative / interview framing</li>
  <li><b>D3 leakage probe</b>: includes pre-outcome scores — shown as an inflation check only</li>
</ul>
Each (participant × config) is rated k={n_runs} times; inter-run SD captures persona stability.
</p>
<p>
<em>Embedder note</em>: The offline demo uses a deterministic char n-gram hashing vectorizer
(no network, no model download). Swap in
<code>SentenceTransformerEmbedder("all-MiniLM-L6-v2")</code> from
<code>eval_pipeline/embedder.py</code> for real use.
</p>

<h2>2. Outcome Instruments</h2>
<ul>
  <li><b>Continuity (FSCS, 3 items)</b>: "How similar/connected/care..." — 1=Not at all, 7=Completely. Mean of 3 items.</li>
  <li><b>Vividness (4 items)</b>: viv_clear/tangible/detail/felt — 1=Strongly disagree, 7=Strongly agree. Mean of 4.</li>
  <li><b>Closeness (IOS, 1 item)</b>: ios_post — 1=Completely separate, 7=Completely overlapping.</li>
  <li><b>Manipulation Checks (3 items)</b>: mc_style/scene/understand — transcript-observable. Mean of 3.</li>
  <li><b>Persuasiveness</b>: NOT collected by the app. Slot reserved; labeled synthetic-only.</li>
</ul>

<h2>3. Results Tables</h2>
<p>Per-outcome × per-depth metrics (prompt structure: <em>structured</em>). Bootstrap 95% CIs shown in brackets.
<span style='color:#d7301f'><b>Red rows = D3 leakage probe (do not use as a real level).</b></span></p>
{table_html}

<div class="leakage-warn">
<b>D3 Leakage Probe explanation:</b> D3 feeds the participant's own <em>pre-session</em> outcome scores
into the persona, inflating level-agreement (Spearman ρ rises) while adding no new information from
the transcript. This demonstrates the anti-circularity risk: including pre-outcome scores in
the persona construction would make agreement metrics look artificially good. D3 is reported here
as a methodological check only and is excluded from all substantive conclusions.
</div>

<h2>4. Figures</h2>

<div class="fig-row">
  <div class="fig-box">
    <h3>Figure 1: Predicted vs Actual (D2, structured)</h3>
    {fig_tags.get('scatter', '<em>Not available</em>')}
  </div>
  <div class="fig-box">
    <h3>Figure 2: Bland-Altman (D2, structured)</h3>
    {fig_tags.get('ba', '<em>Not available</em>')}
  </div>
</div>

<div class="fig-row">
  <div class="fig-box">
    <h3>Figure 3: Agreement by Persona Depth (ablation)</h3>
    {fig_tags.get('depth_ablation', '<em>Not available</em>')}
  </div>
  <div class="fig-box">
    <h3>Figure 4: Level vs Δ-correlation (D2)</h3>
    {fig_tags.get('delta_vs_level', '<em>Not available</em>')}
  </div>
</div>

<div class="fig-row">
  <div class="fig-box">
    <h3>Figure 5: Observable vs Felt Outcomes</h3>
    {fig_tags.get('observable_vs_felt', '<em>Not available</em>')}
  </div>
</div>

<h2>5. Metric Definitions</h2>
<div class="metric-def"><b>MAE</b>: Mean Absolute Error between predicted and actual continuous ratings.</div>
<div class="metric-def"><b>Spearman ρ</b>: Rank correlation between predicted and actual ratings (level-agreement).</div>
<div class="metric-def"><b>QWK</b>: Quadratic-weighted Cohen's κ — penalises large disagreements more than small ones.</div>
<div class="metric-def"><b>ICC(2,1)</b>: Intraclass Correlation Coefficient, two-way random, absolute agreement, single measures.</div>
<div class="metric-def"><b>Adjacent Accuracy</b>: Proportion of predictions within ±1 of the actual rounded rating.</div>
<div class="metric-def"><b>Bland-Altman</b>: Systematic bias (mean difference) and 95% limits of agreement (±1.96 SD of differences).</div>
<div class="metric-def"><b>Δ-correlation</b>: Spearman between (predicted_post − actual_pre) and (actual_post − actual_pre). Measures whether the model captures change from baseline. Expected to be lower than level-correlation.</div>
<div class="metric-def"><b>Inter-run SD</b>: Mean per-participant SD across k={n_runs} repeated runs at the same config (persona stability).</div>
<div class="metric-def"><b>FSCS test-retest context</b>: Literature ceiling ≈ .66 (Ersner-Hershfield, 2009). No test-retest data available in this study → normalized accuracy not computed.</div>

<h2>6. Limitations</h2>
<div class="limitations">
<ul>
  {data_limit}
  <li><b>No test-retest data</b>: Park (2019) normalized accuracy cannot be computed; FSCS test-retest r≈.66 cited as context only.</li>
  <li><b>Single judge model</b>: Only one LLM (FakeLLM here; claude-sonnet-4-6 in production) acts as judge. No inter-model agreement computed.</li>
  <li><b>SSR stub embedder</b>: The offline demo uses a char n-gram hashing vectorizer as a stand-in. Real agreement requires sentence-transformers or equivalent.</li>
  <li><b>Persuasiveness not collected</b>: The app does not export a persuasiveness outcome. The slot is reserved but empty.</li>
  <li><b>Small N</b>: N={n_participants}. Results are descriptive only; no inferential testing.</li>
  <li><b>Model/temperature fixed</b>: Model is constrained to claude-sonnet-4-6 (matches the app). Temperature and seed are varied instead of model; this study does not implement cross-model comparison.</li>
</ul>
</div>

</body>
</html>"""

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
