import numpy as np

from app.services.federated_ring_mask import (
    aggregate_weighted_masked,
    ring_masks,
    verify_zero_sum,
)


def test_ring_masks_sum_to_zero():
    masks = ring_masks(4, 10, seed=42)
    assert verify_zero_sum(masks)
    s = np.zeros(10)
    for m in masks:
        s += m
    assert np.allclose(s, 0.0)


def test_aggregate_weighted_masked():
    v1 = np.ones(3)
    v2 = np.ones(3) * 2
    m = ring_masks(2, 3, seed=0)
    w1 = 3 * v1 + m[0]
    w2 = 5 * v2 + m[1]
    out = aggregate_weighted_masked([w1, w2], [3, 5])
    expected = (3 * v1 + 5 * v2) / 8.0
    assert np.allclose(out, expected)
