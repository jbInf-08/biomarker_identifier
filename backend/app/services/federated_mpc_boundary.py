"""
Boundary for a future full cryptographic secure-aggregation (MPC / Bonawitz-style) engine.

The coordinator in ``federated_learning_service`` still decrypts application-layer
blobs today. A production SecAgg implementation would:

- Run multi-round mask exchange between clients (or use a trusted key broker).
- Aggregate only masked sums or ciphertexts that the server cannot unmask per client.

This module defines a narrow interface so crypto work can live in one place without
scattering protocol state across routes and ORM models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Protocol


class ParticipantUpdateView(Protocol):
    """Minimal read-only view of a stored update (avoid dict coupling)."""

    participant_id: str
    num_samples: int
    meta_data: Dict[str, Any] | None


class SecureAggregationEngine(ABC):
    """Pluggable SecAgg / MPC aggregator (not implemented)."""

    @abstractmethod
    async def aggregate_round(
        self,
        round_id: str,
        updates: List[ParticipantUpdateView],
    ) -> Dict[str, Any]:
        """
        Return globally aggregated weights as a dict of numpy arrays (or raise).

        Implementations must document trust assumptions (honest server, semi-honest,
        malicious, etc.).
        """
        raise NotImplementedError


class TrustedCoordinatorPlaceholder(SecureAggregationEngine):
    """Explicit placeholder: do not use in production for adversarial coordinators."""

    async def aggregate_round(
        self,
        round_id: str,
        updates: List[ParticipantUpdateView],
    ) -> Dict[str, Any]:
        raise NotImplementedError(
            "Install a concrete SecureAggregationEngine; see docs/FEDERATED_FULL_MPC_ROADMAP.md"
        )


def default_engine() -> SecureAggregationEngine:
    """Return the active engine (placeholder until a real implementation is wired)."""
    return TrustedCoordinatorPlaceholder()
