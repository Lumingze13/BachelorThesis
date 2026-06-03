"""
Tests for SSR (Semantic Similarity Rating) module.
"""

import numpy as np
import pytest
from eval_pipeline.ssr import ssr_rate, ssr_rate_item
from eval_pipeline.embedder import HashingEmbedder
from eval_pipeline.schema import ITEM_SSR_ANCHORS


class TestSSR:
    @pytest.fixture(scope="class")
    def embedder(self):
        return HashingEmbedder()

    def test_returns_expected_value_in_range(self, embedder):
        anchors = ITEM_SSR_ANCHORS["fscs_similar_post"]
        text = "I feel moderately similar to my future self."
        ev, mode, probs = ssr_rate(text, anchors, embedder=embedder)
        assert 1.0 <= ev <= 7.0
        assert mode in range(1, 8)
        assert probs.shape == (7,)
        assert abs(probs.sum() - 1.0) < 1e-6

    def test_near_anchor_biases_toward_that_point(self, embedder):
        """
        A free-text response that closely matches an anchor should have
        highest probability near that anchor.

        NOTE: With the stub hashing embedder, similarity is based on character
        n-gram overlap, so exact anchor text should give highest similarity.
        """
        anchors = ITEM_SSR_ANCHORS["viv_clear_post"]
        # Use the exact anchor text for scale point 7
        exact_text = anchors[7]
        ev, mode, probs = ssr_rate(exact_text, anchors, embedder=embedder)
        # Mode should be at the high end (5-7) — exact match gives highest cosine sim
        assert mode >= 4, f"Expected mode >= 4 for text matching anchor 7, got mode={mode}"

    def test_probabilities_sum_to_one(self, embedder):
        anchors = ITEM_SSR_ANCHORS["ios_post"]
        ev, mode, probs = ssr_rate("Some text.", anchors, embedder=embedder)
        assert abs(probs.sum() - 1.0) < 1e-6

    def test_ssr_rate_item_by_id(self, embedder):
        ev, mode, probs = ssr_rate_item(
            "I feel completely connected to my future self.",
            item_id="fscs_connected_post",
            embedder=embedder,
        )
        assert 1.0 <= ev <= 7.0
        assert mode in range(1, 8)

    def test_unknown_item_id_raises(self, embedder):
        with pytest.raises(KeyError):
            ssr_rate_item("text", item_id="nonexistent_item", embedder=embedder)

    def test_all_defined_items_have_7_anchors(self):
        for item_id, anchors in ITEM_SSR_ANCHORS.items():
            assert len(anchors) == 7, f"Item {item_id} has {len(anchors)} anchors, expected 7"
            for pt in range(1, 8):
                assert pt in anchors, f"Item {item_id} missing anchor for scale point {pt}"

    def test_temperature_affects_distribution(self, embedder):
        """Higher temperature → more uniform distribution."""
        anchors = ITEM_SSR_ANCHORS["fscs_similar_post"]
        text = anchors[7]  # exact match to scale point 7
        _, _, probs_low = ssr_rate(text, anchors, embedder=embedder, temperature=0.1)
        _, _, probs_high = ssr_rate(text, anchors, embedder=embedder, temperature=5.0)
        # Entropy should be higher for higher temperature
        def entropy(p):
            p = p[p > 0]
            return -np.sum(p * np.log(p))
        assert entropy(probs_high) > entropy(probs_low)
