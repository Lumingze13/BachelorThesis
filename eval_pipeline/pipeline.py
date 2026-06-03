"""
Core evaluation pipeline.

For each (participant × config):
  1. Build persona prompt at given depth + structure
  2. Call LLM to get free-text SSR response per item
  3. Convert via SSR to continuous rating
  4. Compare vs actual post-survey ratings
  5. Aggregate metrics per outcome

Config dimensions:
  - depth: D0 / D1 / D2 / D3
  - prompt_structure: structured / narrative / interview
  - n_runs (k): number of repeat runs per participant (inter-run SD)
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import logging

from eval_pipeline.schema import OUTCOMES, ITEM_SSR_ANCHORS, DEPTH_LABELS
from eval_pipeline.loader import load_session
from eval_pipeline.persona import build_persona_prompt
from eval_pipeline.ssr import ssr_rate_item
from eval_pipeline.metrics import compute_metrics, compute_interrun_sd
from eval_pipeline.embedder import BaseEmbedder, get_default_embedder
from eval_pipeline.llm_client import BaseLLM

logger = logging.getLogger(__name__)


def _get_actual_post_items(session: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Extract actual post-survey Likert items."""
    post = session.get("postSurvey", {})
    result = {}
    for outcome_cfg in OUTCOMES.values():
        for item_id in outcome_cfg["items"]:
            result[item_id] = post.get(item_id)
    return result


def _get_actual_pre_by_outcome(session: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Return pre-outcome mean for each outcome family."""
    return session.get("outcomes_pre", {})


def run_one_session(
    session: Dict[str, Any],
    depth: str,
    prompt_structure: str,
    llm: BaseLLM,
    embedder: Optional[BaseEmbedder] = None,
    run_id: int = 0,
    ssr_temperature: float = 0.3,
) -> Dict[str, Any]:
    """
    Run the full SSR prediction for one session × config × run_id.

    Returns dict with:
      session_id, depth, prompt_structure, run_id
      predicted_items: {item_id: predicted_continuous_rating}
      predicted_outcomes: {outcome_family: predicted_mean}
      actual_items: {item_id: actual_rating}
      actual_outcomes_post: {outcome_family: actual_mean}
      actual_outcomes_pre: {outcome_family: pre_mean}
    """
    if embedder is None:
        embedder = get_default_embedder()

    session_id = session.get("session_id", "unknown")
    predicted_items: Dict[str, float] = {}
    actual_items = _get_actual_post_items(session)

    for outcome_name, outcome_cfg in OUTCOMES.items():
        item_ids = outcome_cfg["items"]
        item_scale = outcome_cfg["scale"]
        observable = outcome_cfg["observable"]

        # Item text lookup — use anchor text as proxy for item wording
        for item_id in item_ids:
            anchors = ITEM_SSR_ANCHORS.get(item_id, {})
            # Use the mid-point anchor as item text for the prompt
            item_text_for_prompt = anchors.get(4, f"Rate your agreement: {item_id}")

            try:
                prompt = build_persona_prompt(
                    session=session,
                    depth=depth,
                    prompt_structure=prompt_structure,
                    item_id=item_id,
                    item_text=item_text_for_prompt,
                    outcome_family=outcome_name,
                )

                free_text = llm.complete(
                    prompt,
                    depth=depth,
                    session=session,
                    outcome_family=outcome_name,
                    item_id=item_id,
                    run_id=run_id,
                    observable=observable,
                )

                ev, mode, probs = ssr_rate_item(
                    free_text=free_text,
                    item_id=item_id,
                    embedder=embedder,
                    temperature=ssr_temperature,
                )
                predicted_items[item_id] = ev

            except Exception as e:
                logger.warning(f"[pipeline] {session_id} {depth} {item_id} run{run_id}: {e}")
                predicted_items[item_id] = float("nan")

    # Aggregate predicted outcomes
    predicted_outcomes: Dict[str, Optional[float]] = {}
    for outcome_name, outcome_cfg in OUTCOMES.items():
        vals = [predicted_items.get(iid) for iid in outcome_cfg["items"]]
        valid = [v for v in vals if v is not None and not np.isnan(v)]
        predicted_outcomes[outcome_name] = float(np.mean(valid)) if valid else None

    # Aggregate actual post outcomes
    actual_outcomes_post: Dict[str, Optional[float]] = {}
    for outcome_name, outcome_cfg in OUTCOMES.items():
        vals = [actual_items.get(iid) for iid in outcome_cfg["items"]]
        valid = [v for v in vals if v is not None]
        actual_outcomes_post[outcome_name] = float(np.mean(valid)) if valid else None

    return {
        "session_id": session_id,
        "depth": depth,
        "prompt_structure": prompt_structure,
        "run_id": run_id,
        "predicted_items": predicted_items,
        "predicted_outcomes": predicted_outcomes,
        "actual_items": actual_items,
        "actual_outcomes_post": actual_outcomes_post,
        "actual_outcomes_pre": _get_actual_pre_by_outcome(session),
    }


def run_pipeline(
    sessions: List[Dict[str, Any]],
    depths: List[str],
    prompt_structures: List[str],
    llm: BaseLLM,
    embedder: Optional[BaseEmbedder] = None,
    n_runs: int = 5,
    ssr_temperature: float = 0.3,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """
    Run the full pipeline over all sessions × depths × structures × runs.

    Returns flat list of per-session×config×run result dicts.
    """
    results = []
    total = len(sessions) * len(depths) * len(prompt_structures) * n_runs
    done = 0

    for session in sessions:
        for depth in depths:
            for ps in prompt_structures:
                for run_id in range(n_runs):
                    res = run_one_session(
                        session=session,
                        depth=depth,
                        prompt_structure=ps,
                        llm=llm,
                        embedder=embedder,
                        run_id=run_id,
                        ssr_temperature=ssr_temperature,
                    )
                    results.append(res)
                    done += 1
                    if verbose and done % max(1, total // 20) == 0:
                        pct = 100 * done / total
                        print(f"  [{pct:5.1f}%] {done}/{total} complete", flush=True)

    return results


def aggregate_metrics(
    results: List[Dict[str, Any]],
    outcome_names: Optional[List[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Aggregate prediction results into per-(depth × prompt_structure × outcome) metrics.

    Returns nested dict:
      {(depth, prompt_structure, outcome_name): metrics_dict}
    """
    if outcome_names is None:
        outcome_names = list(OUTCOMES.keys())

    # Group results by (depth, prompt_structure)
    from collections import defaultdict
    groups = defaultdict(list)
    for r in results:
        key = (r["depth"], r["prompt_structure"])
        groups[key].append(r)

    aggregated = {}

    for (depth, ps), group_results in groups.items():
        for outcome_name in outcome_names:
            # For each participant, take mean across runs for prediction
            by_session = defaultdict(list)
            for r in group_results:
                pred_val = r["predicted_outcomes"].get(outcome_name)
                actual_val = r["actual_outcomes_post"].get(outcome_name)
                pre_val = r["actual_outcomes_pre"].get(outcome_name)
                run_id = r["run_id"]
                sid = r["session_id"]
                by_session[sid].append({
                    "pred": pred_val,
                    "actual": actual_val,
                    "pre": pre_val,
                    "run_id": run_id,
                })

            # Build arrays
            session_ids = sorted(by_session.keys())
            pred_means = []
            actual_vals = []
            pre_vals = []
            per_run_preds = {}  # run_id -> list

            for sid in session_ids:
                runs = by_session[sid]
                preds = [r["pred"] for r in runs if r["pred"] is not None and not np.isnan(r["pred"])]
                actuals = [r["actual"] for r in runs if r["actual"] is not None]
                pres = [r["pre"] for r in runs if r["pre"] is not None]

                if preds and actuals:
                    pred_means.append(np.mean(preds))
                    actual_vals.append(actuals[0])
                    pre_vals.append(pres[0] if pres else np.nan)

                for r_item in runs:
                    rid = r_item["run_id"]
                    if r_item["pred"] is not None and not np.isnan(r_item["pred"]):
                        per_run_preds.setdefault(rid, []).append(r_item["pred"])

            if len(pred_means) < 2:
                continue

            pred_arr = np.array(pred_means)
            actual_arr = np.array(actual_vals)
            pre_arr = np.array(pre_vals) if any(not np.isnan(p) for p in pre_vals) else None

            metrics = compute_metrics(
                pred=pred_arr,
                actual=actual_arr,
                actual_pre=pre_arr,
                scale_lo=1,
                scale_hi=7,
            )

            # Inter-run SD
            run_arrays = [np.array(v) for v in per_run_preds.values() if len(v) == len(pred_means)]
            if len(run_arrays) >= 2:
                ir_sd = compute_interrun_sd(run_arrays)
                metrics["interrun_sd_mean"] = float(np.nanmean(ir_sd))
            else:
                metrics["interrun_sd_mean"] = float("nan")

            metrics["n_sessions"] = len(pred_means)
            metrics["outcome_name"] = outcome_name
            metrics["depth"] = depth
            metrics["prompt_structure"] = ps

            aggregated[(depth, ps, outcome_name)] = metrics

    return aggregated
