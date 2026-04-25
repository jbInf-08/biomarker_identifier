"""
Bonawitz *style* zero-sum mask vectors (pair-difference / ring) for masked FedAvg.

Used **with** per-update Fernet + TLS: clients add coordinated masks so the sum of
``(n_i * w_i) + m_i`` equals ``sum_i n_i * w_i`` when ``sum_i m_i = 0``. The
server decrypts and sums — the masks are a second layer on top of transport
encryption. See :mod:`app.services.federated_ring_mask` for the construction.
"""

from __future__ import annotations

from app.services.federated_ring_mask import (
    aggregate_weighted_masked,
    ring_masks,
    verify_zero_sum,
)

# Same zero-sum family as in Bonawitz et al. (pairwise canceling terms on a ring).
bonawitz_pairwise_zero_sum_masks = ring_masks

__all__ = [
    "bonawitz_pairwise_zero_sum_masks",
    "verify_zero_sum",
    "aggregate_weighted_masked",
]
