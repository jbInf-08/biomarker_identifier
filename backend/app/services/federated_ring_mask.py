"""
Ring-style zero-sum masks for masked vector aggregation (federated roadmap).

If participant i submits (n_i * v_i) + mask_i with masks from ``ring_masks``,
then sum_i ((n_i * v_i) + mask_i) = sum_i (n_i * v_i) because sum_i mask_i = 0.

Clients must coordinate the seed and ordering; the coordinator only sums ciphertext
or masked tensors and never recovers individual v_i from masked values alone
(without side information). Transport may still use TLS/Fernet separately.
"""

from __future__ import annotations

from typing import List

import numpy as np


def ring_masks(n_participants: int, dim: int, seed: int) -> List[np.ndarray]:
    """
    Build ``n`` vectors with exact zero sum (ring topology: m_i = r_i - r_{i+1}).
    """
    if n_participants < 2:
        raise ValueError("ring_masks requires at least 2 participants")
    rng = np.random.default_rng(seed)
    r = [rng.standard_normal(dim).astype(np.float64) for _ in range(n_participants)]
    masks = [r[i] - r[(i + 1) % n_participants] for i in range(n_participants)]
    return masks


def verify_zero_sum(masks: List[np.ndarray], atol: float = 1e-6) -> bool:
    s = np.zeros_like(masks[0], dtype=np.float64)
    for m in masks:
        s += m
    return bool(np.allclose(s, 0.0, atol=atol))


def aggregate_weighted_masked(
    masked_tensors: List[np.ndarray], num_samples: List[int]
) -> np.ndarray:
    """
    FedAvg-style mean from per-participant tensors of shape (n_i * v_i + mask_i).

    Masks must sum to zero so that sum_i masked_i = sum_i (n_i * v_i).
    """
    if len(masked_tensors) != len(num_samples):
        raise ValueError("masked_tensors and num_samples length mismatch")
    acc = np.zeros_like(masked_tensors[0], dtype=np.float64)
    for t in masked_tensors:
        acc += np.asarray(t, dtype=np.float64)
    total_n = float(sum(num_samples))
    if total_n <= 0:
        raise ValueError("total sample count must be positive")
    return acc / total_n
