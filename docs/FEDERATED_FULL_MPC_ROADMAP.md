# Full cryptographic secure aggregation (MPC) — roadmap

The current server implements **trusted-coordinator** federated learning: updates are decrypted on the server for aggregation. **Ring-masked FedAvg** (`FEDERATED_CRYPTO_SECURE_AGGREGATION_ENABLED` + `meta_data.use_ring_masked`) improves the *math* so masked tensors sum to the true weighted average when masks are coordinated client-side, but the **coordinator still decrypts** Fernet payloads unless clients send only pre-combined sums over a different channel.

## What “full MPC” usually means here

| Property | Trusted coordinator + TLS | Ring masks (this repo) | Bonawitz-style SecAgg |
|----------|---------------------------|------------------------|------------------------|
| Server sees plaintext per-client gradients | Yes | Yes (after decrypt) | **No** (only masked sums) |
| Pairwise / round masks | No | Client-side | Yes, protocol-enforced |
| Malicious dropout handling | N/A | Partial | Protocol-specific |

**Bonawitz et al.** (*Practical Secure Aggregation for Privacy-Preserving Machine Learning*, CCS 2017) — the usual reference for production-grade secure aggregation in federated learning.

## Integration options (research / production)

1. **TensorFlow Federated** / **TensorFlow Privacy** — SecAgg primitives in Python; may require mapping your model weights to TFF structures.
2. **OpenMined PySyft** — federated + encrypted computation; heavier dependency footprint.
3. **Custom Rust/C++ crypto** — implement Shamir + masking in a sidecar; coordinator runs **only** sum aggregation on ciphertexts (needs homomorphic-friendly design or interactive rounds).

## Suggested milestones

1. **Freeze wire format**: document JSON/binary schema for per-layer updates and round IDs.
2. **Isolate crypto**: implement `SecAggRound` state machine in a dedicated module (no SQLAlchemy in crypto layer).
3. **Two-phase rounds**: *mask collection* → *masked sum* without ever materializing all plaintext vectors at once on the server (requires protocol design matching Bonawitz).
4. **Audit**: third-party crypto review before multi-institution clinical data.

## Code hooks in this repository

- `app/services/federated_ring_mask.py` — zero-sum masks for tensor sums.
- `app/services/federated_learning_service.py` — `_federated_ring_masked_average` when flag + metadata are set.
- `app/services/federated_mpc_boundary.py` — placeholder interface for a future SecAgg engine (see file).

## Threat model

See `docs/federated_threat_model.md`. Update it when a real MPC path is merged.
