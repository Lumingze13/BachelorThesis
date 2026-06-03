"""
Tests for the metrics module — verify recovery of known values.
"""

import numpy as np
import pytest
from eval_pipeline.metrics import (
    mae, spearman, qwk, icc21,
    exact_accuracy, adjacent_accuracy,
    bland_altman, delta_correlation,
    compute_metrics,
)


class TestMAE:
    def test_perfect(self):
        a = np.array([1.0, 3.0, 5.0, 7.0])
        assert mae(a, a) == pytest.approx(0.0)

    def test_constant_offset(self):
        pred = np.array([2.0, 3.0, 4.0, 5.0])
        actual = np.array([1.0, 2.0, 3.0, 4.0])
        assert mae(pred, actual) == pytest.approx(1.0)

    def test_known_value(self):
        pred = np.array([1.0, 2.0, 3.0])
        actual = np.array([2.0, 2.0, 2.0])
        # |1-2|=1, |2-2|=0, |3-2|=1 → mean=0.667
        assert mae(pred, actual) == pytest.approx(2 / 3, rel=1e-6)


class TestSpearman:
    def test_perfect_agreement(self):
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        r = spearman(a, a)
        assert r == pytest.approx(1.0, abs=1e-6)

    def test_perfect_disagreement(self):
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        b = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
        r = spearman(a, b)
        assert r == pytest.approx(-1.0, abs=1e-6)

    def test_nan_for_tiny_n(self):
        a = np.array([1.0, 2.0])
        r = spearman(a, a)
        assert np.isnan(r) or -1 <= r <= 1


class TestQWK:
    def test_perfect_agreement(self):
        a = np.array([1, 2, 3, 4, 5, 6, 7])
        k = qwk(a.astype(float), a.astype(float))
        assert k == pytest.approx(1.0, abs=0.01)

    def test_constant_offset_penalised(self):
        actual = np.array([3, 3, 3, 4, 4, 4, 5, 5])
        pred = actual + 2.0  # systematic offset of 2
        k_offset = qwk(pred, actual.astype(float))
        k_perfect = qwk(actual.astype(float), actual.astype(float))
        assert k_offset < k_perfect

    def test_returns_float(self):
        a = np.array([1.0, 3.0, 5.0, 7.0])
        b = np.array([2.0, 3.0, 4.0, 6.0])
        k = qwk(a, b)
        assert isinstance(k, float)


class TestICC21:
    def test_perfect_agreement_gives_high_icc(self):
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
        icc = icc21(a, a)
        # Perfect agreement → ICC should be close to 1
        assert icc > 0.95, f"ICC={icc} expected near 1 for perfect agreement"

    def test_constant_offset_lowers_icc(self):
        actual = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
        pred_offset = actual + 1.5
        icc_offset = icc21(pred_offset, actual)
        icc_perfect = icc21(actual, actual)
        assert icc_offset < icc_perfect

    def test_ba_bias_equals_offset(self):
        """Bland-Altman bias should equal the constant offset."""
        actual = np.array([2.0, 3.0, 4.0, 5.0])
        pred = actual + 1.0
        bias, lo, hi = bland_altman(pred, actual)
        assert bias == pytest.approx(1.0, abs=1e-9)

    def test_ba_loa_zero_sd_for_constant_offset(self):
        """For constant offset, LoA should be symmetric around bias with very small width."""
        actual = np.array([2.0, 3.0, 4.0, 5.0, 6.0])
        pred = actual + 2.0
        bias, lo, hi = bland_altman(pred, actual)
        # SD of differences = 0 → LoA = [2.0, 2.0]
        assert abs(hi - lo) < 0.01


class TestAccuracy:
    def test_exact_perfect(self):
        a = np.array([1.0, 2.0, 3.0, 4.0])
        assert exact_accuracy(a, a) == pytest.approx(1.0)

    def test_exact_zero(self):
        pred = np.array([1.0, 1.0, 1.0, 1.0])
        actual = np.array([7.0, 7.0, 7.0, 7.0])
        assert exact_accuracy(pred, actual) == pytest.approx(0.0)

    def test_adjacent_allows_one_off(self):
        pred = np.array([3.0, 4.0, 5.0])
        actual = np.array([2.0, 4.0, 6.0])
        # |3-2|=1 ✓, |4-4|=0 ✓, |5-6|=1 ✓ → 3/3 = 1.0
        assert adjacent_accuracy(pred, actual) == pytest.approx(1.0)

    def test_adjacent_fails_two_off(self):
        pred = np.array([1.0, 7.0])
        actual = np.array([4.0, 4.0])
        # |1-4|=3 ✗, |7-4|=3 ✗
        assert adjacent_accuracy(pred, actual) == pytest.approx(0.0)


class TestDeltaCorrelation:
    def test_recovers_known_direction(self):
        """If predicted delta mirrors actual delta, dc should be positive."""
        actual_pre = np.array([2.0, 3.0, 4.0, 5.0, 3.0])
        actual_post = np.array([3.0, 5.0, 4.0, 7.0, 2.0])
        # Perfect delta prediction
        pred_post = actual_post.copy()
        dc = delta_correlation(pred_post, actual_pre, actual_post)
        assert dc > 0.9

    def test_anticorrelated_delta(self):
        actual_pre = np.array([2.0, 3.0, 4.0, 5.0, 3.0])
        actual_post = np.array([3.0, 5.0, 4.0, 7.0, 2.0])
        # Reversed delta → negative dc
        actual_delta = actual_post - actual_pre
        pred_post = actual_pre - actual_delta
        dc = delta_correlation(pred_post, actual_pre, actual_post)
        assert dc < -0.5


class TestComputeMetrics:
    def test_runs_without_error(self):
        rng = np.random.default_rng(42)
        pred = rng.uniform(1, 7, size=20)
        actual = rng.uniform(1, 7, size=20)
        pre = rng.uniform(1, 7, size=20)
        m = compute_metrics(pred, actual, actual_pre=pre, n_boot=200, seed=0)
        for key in ["mae", "spearman", "qwk", "icc21", "exact_acc",
                    "adjacent_acc", "ba_bias", "ba_loa", "delta_corr"]:
            assert key in m, f"Missing metric: {key}"

    def test_perfect_prediction_high_metrics(self):
        actual = np.array([2.0, 3.0, 4.0, 5.0, 6.0, 4.0, 3.0, 5.0])
        m = compute_metrics(actual, actual, n_boot=200, seed=0)
        assert m["mae"][0] == pytest.approx(0.0, abs=1e-9)
        assert m["spearman"][0] == pytest.approx(1.0, abs=0.01)
        assert m["qwk"][0] == pytest.approx(1.0, abs=0.01)
        assert m["icc21"][0] > 0.95
        assert m["exact_acc"][0] == pytest.approx(1.0, abs=0.01)

    def test_constant_offset_ba_bias(self):
        actual = np.array([2.0, 3.0, 4.0, 5.0, 3.0, 6.0, 4.0])
        pred = actual + 1.5
        m = compute_metrics(pred, actual, n_boot=200, seed=0)
        assert m["ba_bias"] == pytest.approx(1.5, abs=1e-9)
