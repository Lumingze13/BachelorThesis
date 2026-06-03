"""
Tests for the session loader.
"""

import json
import os
import tempfile
import pytest
import numpy as np

from eval_pipeline.synth import SyntheticGenerator
from eval_pipeline.loader import load_session, extract_item_scores


@pytest.fixture(scope="module")
def sample_session_path(tmp_path_factory):
    """Generate and save one synthetic session; return path."""
    gen = SyntheticGenerator(n=1, seed=0)
    sessions = gen.generate()
    sess = sessions[0]
    # Save without _latent
    saveable = {k: v for k, v in sess.items() if k != "_latent"}
    tmp = tmp_path_factory.mktemp("data")
    path = str(tmp / "test_session.json")
    with open(path, "w") as f:
        json.dump(saveable, f)
    return path


@pytest.fixture(scope="module")
def loaded(sample_session_path):
    return load_session(sample_session_path)


class TestLoader:
    def test_session_id_set(self, loaded):
        assert loaded["session_id"] == "test_session"

    def test_top_level_keys(self, loaded):
        for key in ["meta", "profile", "preSurvey", "scores", "phaseB", "phaseC", "postSurvey"]:
            assert key in loaded, f"Missing top-level key: {key}"

    def test_outcomes_pre_computed(self, loaded):
        pre = loaded["outcomes_pre"]
        assert "continuity" in pre
        assert "vividness" in pre
        assert "closeness" in pre
        # Values should be in [1,7]
        for k, v in pre.items():
            if v is not None:
                assert 1.0 <= v <= 7.0, f"outcomes_pre[{k}]={v} out of range"

    def test_outcomes_post_computed(self, loaded):
        post = loaded["outcomes_post"]
        assert "continuity" in post
        assert "vividness" in post
        assert "closeness" in post
        assert "manip_checks" in post
        for k, v in post.items():
            if v is not None:
                assert 1.0 <= v <= 7.0, f"outcomes_post[{k}]={v} out of range"

    def test_persuasiveness_slot_present(self, loaded):
        # Persuasiveness slot should exist and be None
        assert "persuasiveness" in loaded["outcomes_post"]
        assert loaded["outcomes_post"]["persuasiveness"] is None

    def test_extract_item_scores(self, loaded):
        items = extract_item_scores(loaded)
        # Should have all post-survey Likert item IDs
        from eval_pipeline.schema import OUTCOMES
        for outcome_cfg in OUTCOMES.values():
            for item_id in outcome_cfg["items"]:
                assert item_id in items, f"Missing item: {item_id}"

    def test_meta_fields(self, loaded):
        assert "condition" in loaded["meta"]
        assert loaded["meta"]["condition"] in ("main", "baseline")

    def test_phase_b_transcript_nonempty(self, loaded):
        transcript = loaded["phaseB"]["transcript"]
        assert isinstance(transcript, list)
        assert len(transcript) >= 1

    def test_scores_bigfive(self, loaded):
        bf = loaded["scores"]["bigFive"]
        for trait in ["O", "C", "E", "A", "N"]:
            assert trait in bf
            assert 1.0 <= bf[trait] <= 5.0
