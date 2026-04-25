"""
Reports which federated privacy guarantees are actually implemented vs planned.

See docs/PRODUCT_ROADMAP.md and docs/federated_threat_model.md.
"""

from typing import Any, Dict

from app.core.config import settings


def get_federated_privacy_capabilities() -> Dict[str, Any]:
    """Static capability payload for API clients (honest about limitations)."""
    bz = bool(
        getattr(settings, "FEDERATED_BONAWITZ_MASK_AGGREGATION_ENABLED", False)
    )
    return {
        "application_layer_encryption": True,
        "fernet_pickle_wrapping": True,
        "coordinator_decrypts_updates_before_aggregation": True,
        "ring_masked_aggregation_utils": {
            "implemented": True,
            "module": "app.services.federated_ring_mask",
            "notes": (
                "Zero-sum ring masks for weighted tensor sums; clients coordinate seed. "
            ),
        },
        "bonawitz_style_masked_aggregation": {
            "implemented": bz,
            "module": "app.services.federated_bonawitz_mask",
            "config_flag": "FEDERATED_BONAWITZ_MASK_AGGREGATION_ENABLED",
            "client_meta": "use_bonawitz_mask",
            "notes": (
                "Same zero-sum mask math as the ring path; use alongside Fernet transport. "
            ),
        },
        "cryptographic_secure_aggregation": {
            "implemented": bool(
                getattr(settings, "FEDERATED_CRYPTO_SECURE_AGGREGATION_ENABLED", False)
            ),
            "ring_masked_fedavg": bool(
                getattr(settings, "FEDERATED_CRYPTO_SECURE_AGGREGATION_ENABLED", False)
            ),
            "bonawitz_mask_aggregation": bz,
            "notes": (
                "When flags are enabled, set meta_data.use_ring_masked or use_bonawitz_mask; "
                "updates are (n_i*w_i+mask_i) after Fernet decrypt, then averaged."
            ),
        },
        "fedprox": {
            "config_field": "fedprox_mu",
            "env_default": getattr(settings, "FEDERATED_FEDPROX_MU", 0.01),
            "notes": "Applies in participant local training; server aggregates weighted means.",
        },
        "differential_privacy_noise": True,
        "experimental_crypto_flag": getattr(
            settings, "FEDERATED_CRYPTO_SECURE_AGGREGATION_ENABLED", False
        ),
    }
