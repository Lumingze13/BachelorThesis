"""
Pluggable LLM client.

- FakeLLM (default, offline, deterministic given seed):
    Computes a target rating from depth-appropriate latent signal + controlled Gaussian
    noise, then returns the corresponding SSR anchor text (possibly slightly perturbed)
    so the SSR step reliably recovers the target.  This is the offline stub; the key
    property is that deeper depths give predictions closer to the planted truth.

- RealLLMClaude: Anthropic adapter (NOT called in demo/tests; requires ANTHROPIC_API_KEY)
- RealLLMOpenAI: OpenAI-compatible adapter (requires OPENAI_BASE_URL + OPENAI_API_KEY + model)

Only FakeLLM is used when running offline demo or tests.
"""

import os
from typing import Dict, Any, Optional, List
import numpy as np

from eval_pipeline.schema import ITEM_SSR_ANCHORS


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class BaseLLM:
    def complete(self, prompt: str, **kwargs) -> str:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# FakeLLM
# ---------------------------------------------------------------------------

class FakeLLM(BaseLLM):
    """
    Deterministic offline LLM for demo and testing.

    Strategy: compute a noisy target rating (float in [1,7]) from the
    depth-appropriate latent signal, then return the SSR anchor text for the
    nearest integer scale point.  A small perturbation (random word insertions)
    is added so that the free text is not identical to the anchor, while still
    sharing enough character n-grams that the HashingEmbedder correctly ranks
    it highest for that scale point.

    Agreement gradient guarantee (by construction):
      D0 → large noise → predictions scatter around the mean → low ρ
      D1 → trait signal + medium noise → moderate ρ
      D2 → trait + transcript quality signal + small noise → highest ρ
      D3 → pre-outcome value + tiny noise → inflated ρ (leakage)
      manip_checks at D2 → convo_quality signal directly → better ρ than felt
    """

    # Noise std devs (in rating units) by depth.
    # Tuned so signal-to-noise ratio is cleanly ordered D0 < D1 < D2 < D3
    # given the latent signal variances in the synthetic data.
    _NOISE = {
        "D0": 2.0,   # near-chance; large noise dominates
        "D1": 0.90,  # moderate; psych-trait signal gets through
        "D2": 0.45,  # good; psych + transcript quality
        "D3": 0.15,  # inflated; pre-outcome used directly (tiny noise)
    }
    # manip_checks at D2: directly from convo_quality (transcript-observable → tighter)
    _OBSERVABLE_NOISE_D2 = 0.20

    def __init__(self, seed: int = 42, temperature: float = 0.7):
        self.seed = seed
        self.temperature = temperature

    def _child_rng(self, *salt_parts) -> np.random.Generator:
        """Deterministic child RNG from seed + string salts."""
        combined = str(self.seed) + "|".join(str(s) for s in salt_parts)
        h = abs(hash(combined)) % (2 ** 32)
        return np.random.default_rng(h)

    def _compute_target(
        self,
        depth: str,
        session: Dict[str, Any],
        outcome_family: str,
        item_id: str,
        run_id: int,
        observable: bool,
    ) -> float:
        """Return a noisy predicted rating (float in [1,7]) for this config."""
        rng = self._child_rng(
            session.get("session_id", ""),
            depth, outcome_family, item_id, run_id,
        )
        latent = session.get("_latent", {})
        outcomes_pre = session.get("outcomes_pre", {})
        pre = session.get("preSurvey", {})

        traits = latent.get("traits", [3.0, 3.0, 3.0, 3.0, 3.0])
        O, C, E, A, N = [float(t) for t in traits[:5]]
        convo_quality = float(latent.get("convo_quality", 0.5))

        # Amplified convo effect: maps [0,1] → [-1.0, +1.0] around the psych baseline
        convo_effect = 2.0 * (convo_quality - 0.5)  # ∈ [-1, +1]

        if depth == "D0":
            # No real signal — predict grand mean with large noise.
            target = 4.0 + float(rng.normal(0, self._NOISE["D0"]))

        elif depth == "D1":
            # Psychometric signal only (no transcript).
            # Amplified weights so the signal variance is meaningful.
            if outcome_family == "continuity":
                signal = 4.0 + 0.80 * (A - 3.0) + 0.40 * (O - 3.0)
            elif outcome_family == "vividness":
                signal = 4.0 + 0.80 * (O - 3.0) + 0.40 * (E - 3.0)
            elif outcome_family == "closeness":
                signal = 4.0 + 0.80 * (A - 3.0) + 0.30 * (E - 3.0)
            else:  # manip_checks — traits don't predict this; midpoint + noise
                signal = 4.0
            target = signal + float(rng.normal(0, self._NOISE["D1"]))

        elif depth == "D2":
            # Psychometrics + transcript quality signal.
            if outcome_family == "manip_checks" or observable:
                # Transcript-observable: directly from convo_quality
                signal = 1.0 + 6.0 * convo_quality
                noise_std = self._OBSERVABLE_NOISE_D2
            else:
                if outcome_family == "continuity":
                    psych = 4.0 + 0.80 * (A - 3.0) + 0.40 * (O - 3.0)
                elif outcome_family == "vividness":
                    psych = 4.0 + 0.80 * (O - 3.0) + 0.40 * (E - 3.0)
                else:  # closeness
                    psych = 4.0 + 0.80 * (A - 3.0) + 0.30 * (E - 3.0)
                signal = psych + convo_effect  # adds transcript quality on top
                noise_std = self._NOISE["D2"]
            target = signal + float(rng.normal(0, noise_std))

        elif depth == "D3":
            # LEAKAGE PROBE: use pre-outcome score directly (tiny noise).
            pre_val = outcomes_pre.get(outcome_family)
            if pre_val is None or not isinstance(pre_val, (int, float)):
                pre_val = float(pre.get("ios_pre", 4.0)) if outcome_family == "closeness" else 4.0
            target = float(pre_val) + float(rng.normal(0, self._NOISE["D3"]))

        else:
            target = 4.0

        return float(np.clip(target, 1.0, 7.0))

    def complete(self, prompt: str, **kwargs) -> str:
        """
        Generate a free-text SSR response.

        Accepted kwargs:
          depth          : "D0"–"D3"
          session        : loaded session dict (with _latent)
          outcome_family : "continuity" | "vividness" | "closeness" | "manip_checks"
          item_id        : e.g. "fscs_similar_post"
          run_id         : int (0…k-1)
          observable     : bool
        """
        depth = kwargs.get("depth", "D1")
        session = kwargs.get("session", {})
        outcome_family = kwargs.get("outcome_family", "continuity")
        item_id = kwargs.get("item_id", "")
        run_id = int(kwargs.get("run_id", 0))
        observable = bool(kwargs.get("observable", False))

        target_rating = self._compute_target(
            depth, session, outcome_family, item_id, run_id, observable
        )

        # Map to the nearest integer scale point in [1,7]
        scale_point = int(np.clip(round(target_rating), 1, 7))

        # Retrieve the anchor text for that scale point and item
        anchors = ITEM_SSR_ANCHORS.get(item_id, {})
        anchor_text = anchors.get(scale_point, f"I would rate this around {scale_point} out of 7.")

        # Embed the precise target rating as a sentinel tag so that the SSR
        # pass-through path can recover the exact planted value.  This is the
        # offline stub contract; real LLMs never emit this tag.
        sentinel = f"[[SSR_RATING:{target_rating:.4f}]]"

        # Readable prefix so the full response looks like natural language
        prefixes = [
            "Reflecting on the session, I think: ",
            "Honestly speaking, ",
            "After thinking about it carefully, ",
            "My genuine feeling is that ",
        ]
        rng2 = self._child_rng(session.get("session_id", ""), item_id, run_id, "prefix")
        prefix = prefixes[int(rng2.integers(0, len(prefixes)))]

        return f"{prefix}{anchor_text} {sentinel}"

    def __repr__(self) -> str:
        return f"FakeLLM(seed={self.seed}, temperature={self.temperature})"


# ---------------------------------------------------------------------------
# Real LLM adapters (NOT called in demo/tests)
# ---------------------------------------------------------------------------

class RealLLMClaude(BaseLLM):
    """
    Anthropic Claude adapter.
    Requires env var: ANTHROPIC_API_KEY
    Model: claude-sonnet-4-6 (matches the app)
    NOT called during offline demo or tests.
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set")
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            )

    def complete(self, prompt: str, **kwargs) -> str:
        temperature = kwargs.get("temperature", 0.7)
        response = self._client.messages.create(
            model=self.model,
            max_tokens=256,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()


class RealLLMOpenAI(BaseLLM):
    """
    OpenAI-compatible adapter (e.g., UvA OpenAI endpoint).
    Requires env vars: OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL
    NOT called during offline demo or tests.
    """

    def __init__(self):
        base_url = os.environ.get("OPENAI_BASE_URL")
        api_key = os.environ.get("OPENAI_API_KEY")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        if not base_url or not api_key:
            raise EnvironmentError("OPENAI_BASE_URL and OPENAI_API_KEY must be set")
        try:
            from openai import OpenAI
            self._client = OpenAI(base_url=base_url, api_key=api_key)
        except ImportError:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )

    def complete(self, prompt: str, **kwargs) -> str:
        temperature = kwargs.get("temperature", 0.7)
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=256,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()


def get_llm(use_real: bool = False, **kwargs) -> BaseLLM:
    """
    Factory. Returns FakeLLM by default (offline).
    If use_real=True AND env vars are set, returns the appropriate real LLM.
    """
    if not use_real:
        return FakeLLM(**kwargs)
    if os.environ.get("ANTHROPIC_API_KEY"):
        return RealLLMClaude()
    if os.environ.get("OPENAI_BASE_URL") and os.environ.get("OPENAI_API_KEY"):
        return RealLLMOpenAI()
    raise EnvironmentError(
        "use_real=True but no LLM env vars found. "
        "Set ANTHROPIC_API_KEY or OPENAI_BASE_URL+OPENAI_API_KEY."
    )
