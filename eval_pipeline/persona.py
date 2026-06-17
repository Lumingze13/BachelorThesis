"""
Persona / digital-twin prompt builder.

Constructs the LLM system prompt for a participant at a given PERSONA DEPTH.
Anti-circularity guard: asserts no pre-outcome or post-outcome field ID appears
in D0–D2 prompts.
"""

from typing import Dict, Any, List, Optional
from eval_pipeline.schema import (
    PRE_OUTCOME_FIELDS, POST_OUTCOME_FIELDS, DEPTH_LABELS,
)


# ---------------------------------------------------------------------------
# Anti-circularity guard
# ---------------------------------------------------------------------------

_ALL_FORBIDDEN_FOR_D0_D2 = PRE_OUTCOME_FIELDS | POST_OUTCOME_FIELDS


def assert_no_leakage(prompt_text: str, depth: str) -> None:
    """
    Raise AssertionError if any forbidden field ID appears verbatim in the
    persona prompt for depths D0, D1, D2.
    D3 is exempt (it's the explicit leakage probe).
    """
    if depth == "D3":
        return
    for field_id in _ALL_FORBIDDEN_FOR_D0_D2:
        if field_id in prompt_text:
            raise AssertionError(
                f"ANTI-CIRCULARITY VIOLATION: field '{field_id}' found in "
                f"{depth} persona prompt. Pre/post outcome items must not appear "
                f"in persona construction for depths D0-D2."
            )


# ---------------------------------------------------------------------------
# Persona builders per depth
# ---------------------------------------------------------------------------

def _build_d0(session: Dict[str, Any]) -> str:
    """D0: demographics only."""
    pre = session.get("preSurvey", {})
    profile = session.get("profile", {})
    phase_b = session.get("phaseB", {})

    age = pre.get("age", "unknown")
    gender = pre.get("gender", "unknown")
    year = pre.get("year", "unknown")
    major = (pre.get("major") or "").strip()
    name = profile.get("name", "the participant")
    career = phase_b.get("career", "unknown career")

    studying = f" studying {major}" if major else ""
    return (
        f"You are playing the role of {name}, a {age}-year-old {gender} university student "
        f"in their {year} year{studying}. "
        f"They participated in a future-self career exercise focused on the career path: {career}. "
        "Respond as this person would, based only on these demographic details."
    )


def _build_d1(session: Dict[str, Any]) -> str:
    """D1: D0 + psychometrics (BFI/RIASEC/values) + career familiarity."""
    base = _build_d0(session)
    pre = session.get("preSurvey", {})
    scores = session.get("scores", {})
    phase_b = session.get("phaseB", {})

    # Big Five scores (from computed scores section)
    bf = scores.get("bigFive", {})
    bf_str = (
        f"Openness={bf.get('O','?'):.1f}, Conscientiousness={bf.get('C','?'):.1f}, "
        f"Extraversion={bf.get('E','?'):.1f}, Agreeableness={bf.get('A','?'):.1f}, "
        f"Neuroticism={bf.get('N','?'):.1f}"
        if all(isinstance(bf.get(k), (int, float)) for k in ['O','C','E','A','N'])
        else "Big Five scores not available"
    )

    # RIASEC
    ria = scores.get("riasec", {})
    ria_str = (
        f"Realistic={ria.get('R','?'):.1f}, Investigative={ria.get('I','?'):.1f}, "
        f"Artistic={ria.get('A','?'):.1f}, Social={ria.get('S','?'):.1f}, "
        f"Enterprising={ria.get('E','?'):.1f}, Conventional={ria.get('C','?'):.1f}"
        if all(isinstance(ria.get(k), (int, float)) for k in ['R','I','A','S','E','C'])
        else "RIASEC scores not available"
    )

    # Values
    values = scores.get("values", pre.get("values", []))
    values_str = ", ".join(values) if values else "not specified"

    # Career familiarity and interest
    familiarity = phase_b.get("familiarity", "?")
    interest = phase_b.get("interestStrength", "?")

    return (
        f"{base}\n\n"
        f"Personality (Big Five, 1-5 scale): {bf_str}.\n"
        f"Career interests (RIASEC, 1-5): {ria_str}.\n"
        f"Core values: {values_str}.\n"
        f"Career familiarity (1-7): {familiarity}. "
        f"Career interest strength (1-7): {interest}."
    )


def _build_d2(session: Dict[str, Any]) -> str:
    """D2: D1 + participant's own words from phaseB user turns."""
    base = _build_d1(session)
    phase_b = session.get("phaseB", {})
    transcript = phase_b.get("transcript", [])

    user_turns = [
        turn["text"].strip()
        for turn in transcript
        if turn.get("role") == "user" and turn.get("text", "").strip()
    ]

    if not user_turns:
        own_words = "(No phaseB user turns available)"
    else:
        # Keep up to 600 chars of their own words to avoid prompt bloat
        combined = " | ".join(user_turns)
        if len(combined) > 600:
            combined = combined[:597] + "..."
        own_words = combined

    return (
        f"{base}\n\n"
        f"Participant's own words from the career exploration phase:\n"
        f"\"{own_words}\""
    )


def _build_d3(session: Dict[str, Any]) -> str:
    """
    D3: D2 + pre-outcome scores.
    LEAKAGE PROBE ONLY — NOT a recommended persona level.
    Used to demonstrate inflation of agreement when pre-outcome scores are visible.
    """
    base = _build_d2(session)
    pre = session.get("preSurvey", {})
    outcomes_pre = session.get("outcomes_pre", {})

    ios_pre = pre.get("ios_pre", "?")
    fscs_mean = outcomes_pre.get("continuity", "?")
    viv_mean = outcomes_pre.get("vividness", "?")

    fscs_str = f"{fscs_mean:.2f}" if isinstance(fscs_mean, float) else str(fscs_mean)
    viv_str = f"{viv_mean:.2f}" if isinstance(viv_mean, float) else str(viv_mean)

    return (
        f"{base}\n\n"
        f"[LEAKAGE PROBE — pre-session outcome scores included for inflation check]\n"
        f"Pre-session self-reported closeness to future self (IOS, 1-7): {ios_pre}.\n"
        f"Pre-session future-self continuity mean (FSCS, 1-7): {fscs_str}.\n"
        f"Pre-session vividness mean (1-7): {viv_str}."
    )


# ---------------------------------------------------------------------------
# Prompt structure wrappers
# ---------------------------------------------------------------------------

def _wrap_structured(persona_core: str, item_label: str, item_text: str, scale_lo: str, scale_hi: str) -> str:
    return (
        f"[SYSTEM — persona]\n{persona_core}\n\n"
        f"[TASK]\n"
        f"You are filling in a post-session survey AS this participant.\n"
        f"Survey item: \"{item_text}\"\n"
        f"Scale: 1 = {scale_lo}, 7 = {scale_hi}.\n"
        f"First, write 1-2 sentences reflecting how this participant would genuinely feel "
        f"about this after their session. Then state your answer."
    )


def _wrap_narrative(persona_core: str, item_label: str, item_text: str, scale_lo: str, scale_hi: str) -> str:
    return (
        f"{persona_core}\n\n"
        f"After finishing the career chatbot session, {item_text.lower()} "
        f"Think about what this person just experienced and narrate how they feel. "
        f"Describe their feeling in 1-2 sentences as if you are them."
    )


def _wrap_interview(persona_core: str, item_label: str, item_text: str, scale_lo: str, scale_hi: str) -> str:
    return (
        f"{persona_core}\n\n"
        f"Interviewer: \"Now that your session is complete — {item_text.lower()} "
        f"Please answer on a scale from 1 ({scale_lo}) to 7 ({scale_hi}).\"\n"
        f"Participant (you):"
    )


_WRAPPERS = {
    "structured": _wrap_structured,
    "narrative": _wrap_narrative,
    "interview": _wrap_interview,
}

# Scale endpoint labels per item (for prompt wording)
_SCALE_ENDPOINTS = {
    "continuity": ("Not at all", "Completely"),
    "vividness": ("Strongly disagree", "Strongly agree"),
    "closeness": ("Completely separate", "Completely overlapping"),
    "manip_checks": ("Strongly disagree", "Strongly agree"),
}


def build_persona_prompt(
    session: Dict[str, Any],
    depth: str,
    prompt_structure: str,
    item_id: str,
    item_text: str,
    outcome_family: str,
) -> str:
    """
    Build the full persona prompt for a single survey item.

    Parameters
    ----------
    session         : loaded session dict
    depth           : "D0" | "D1" | "D2" | "D3"
    prompt_structure: "structured" | "narrative" | "interview"
    item_id         : e.g. "fscs_similar_post"
    item_text       : the survey item wording
    outcome_family  : e.g. "continuity"

    Returns
    -------
    Full prompt string ready to send to an LLM.
    """
    builders = {"D0": _build_d0, "D1": _build_d1, "D2": _build_d2, "D3": _build_d3}
    if depth not in builders:
        raise ValueError(f"Unknown depth: {depth}. Must be one of {list(builders)}")

    persona_core = builders[depth](session)

    wrapper = _WRAPPERS.get(prompt_structure)
    if wrapper is None:
        raise ValueError(f"Unknown prompt_structure: {prompt_structure}")

    scale_lo, scale_hi = _SCALE_ENDPOINTS.get(outcome_family, ("1", "7"))

    full_prompt = wrapper(persona_core, item_id, item_text, scale_lo, scale_hi)

    # Anti-circularity check (skipped for D3 which is the leakage probe)
    assert_no_leakage(full_prompt, depth)

    return full_prompt


def get_persona_core(session: Dict[str, Any], depth: str) -> str:
    """Return just the persona core (without item wrapper). Used for inspection."""
    builders = {"D0": _build_d0, "D1": _build_d1, "D2": _build_d2, "D3": _build_d3}
    if depth not in builders:
        raise ValueError(f"Unknown depth: {depth}")
    core = builders[depth](session)
    assert_no_leakage(core, depth)
    return core
