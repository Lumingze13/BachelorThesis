"""
SSR — Semantic Similarity Rating module.

Given a free-text response from the persona-LLM and a set of anchor statements
(one per scale point), compute:
  - cosine similarity to each anchor
  - softmax → probability distribution
  - expected value (continuous rating)
  - mode (discrete rating, argmax)

Fully offline — uses the pluggable embedder (default: HashingEmbedder).

Stub-mode pass-through
----------------------
When the FakeLLM is used (offline demo / tests), it encodes the target scale
point directly in the response as a sentinel tag ``[[SSR_RATING:X.XX]]``.
``ssr_rate`` detects this tag and returns the encoded value directly,
bypassing the embedding step.  This lets the synthetic-truth pipeline
faithfully transmit the planted signal without requiring a semantically
meaningful embedder.  The embedding path is still exercised fully when a
real LLM is used (no sentinel present).
"""

import re
from typing import Dict, Optional, Tuple
import numpy as np

from eval_pipeline.embedder import BaseEmbedder, get_default_embedder

# Sentinel pattern written by FakeLLM and parsed here
_SENTINEL_RE = re.compile(r"\[\[SSR_RATING:([\d.]+)\]\]")


def _softmax(x: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64) / temperature
    x = x - np.max(x)
    e = np.exp(x)
    return e / e.sum()


def ssr_rate(
    free_text: str,
    anchors: Dict[int, str],
    embedder: Optional[BaseEmbedder] = None,
    temperature: float = 0.3,
) -> Tuple[float, int, np.ndarray]:
    """
    Rate a free-text response against anchor statements using cosine similarity + softmax.

    Parameters
    ----------
    free_text  : LLM-generated free-text response to the survey item.
                 If it contains ``[[SSR_RATING:X.XX]]`` (FakeLLM stub), the
                 encoded value is returned directly without embedding.
    anchors    : dict mapping scale_point (int) -> anchor statement string
    embedder   : BaseEmbedder instance; defaults to HashingEmbedder
    temperature: softmax temperature (lower = sharper; default 0.3 for stub embedder)

    Returns
    -------
    expected_value : float (continuous rating in anchor key range)
    mode           : int (scale point with highest probability)
    probs          : np.ndarray of shape (n_points,) probabilities
    """
    scale_points = sorted(anchors.keys())
    n = len(scale_points)

    # --- Stub pass-through: sentinel from FakeLLM ---
    m = _SENTINEL_RE.search(free_text)
    if m:
        ev = float(np.clip(float(m.group(1)), min(scale_points), max(scale_points)))
        mode = int(np.clip(round(ev), min(scale_points), max(scale_points)))
        # Build a sharp probability distribution centred on the encoded value
        pts = np.array(scale_points, dtype=float)
        # Gaussian-shaped probs with σ=0.6 around ev
        log_probs = -0.5 * ((pts - ev) / 0.6) ** 2
        probs = _softmax(log_probs, temperature=1.0)
        return ev, mode, probs

    # --- Real path: cosine similarity → softmax ---
    if embedder is None:
        embedder = get_default_embedder()

    anchor_texts = [anchors[k] for k in scale_points]
    response_vec = embedder.embed(free_text)
    anchor_vecs = embedder.embed_batch(anchor_texts)

    sims = np.array([
        embedder.cosine_similarity(response_vec, av) for av in anchor_vecs
    ])

    probs = _softmax(sims, temperature=temperature)
    mode_idx = int(np.argmax(probs))
    mode = scale_points[mode_idx]
    expected_value = float(np.dot(probs, np.array(scale_points, dtype=float)))

    return expected_value, mode, probs


def ssr_rate_item(
    free_text: str,
    item_id: str,
    embedder: Optional[BaseEmbedder] = None,
    temperature: float = 0.3,
) -> Tuple[float, int, np.ndarray]:
    """
    Convenience wrapper: look up anchors by item_id from schema and call ssr_rate.
    """
    from eval_pipeline.schema import ITEM_SSR_ANCHORS
    anchors = ITEM_SSR_ANCHORS.get(item_id)
    if anchors is None:
        raise KeyError(f"No SSR anchors defined for item_id='{item_id}'")
    return ssr_rate(free_text, anchors, embedder=embedder, temperature=temperature)
