# Federated learning — threat model (summary)

## Transport encryption (TLS)

- **What it protects:** Eavesdropping and tampering on the wire between clients and the coordinator API.
- **What it does not prove:** Cryptographic *secure aggregation* of gradients; participants still send updates visible to the server unless a proper MPC/secure-agg protocol is implemented.

## “Secure aggregation” in this codebase

- Updates are **encrypted at rest** in the database using application-level encryption; aggregation runs on the **server** after decryption.
- This is **not** the same as industry secure aggregation where the server only sees masked sums. Treat as **research / demo** unless you add a real protocol (e.g. Bonawitz et al.).

## Multi-worker / horizontal scaling

- The in-memory `global_model` is **per process**. Use **single worker** for demos or persist the global weights (see `FederatedGlobalModel`) and reload orchestration.

## API keys (`X-API-Key`)

- Intended for **automation / site-to-site** calls. Store **hashed** keys only (`ServiceApiKey`), rotate on compromise, and set `FEDERATED_REQUIRE_API_KEY=true` when exposing the Internet.

## Roadmap: cryptographic secure aggregation

The coordinator today decrypts participant updates before averaging. For **production** multi-institution genomics (or adversarial coordinators), adopt a **secure aggregation** protocol (e.g. Bonawitz et al., CCS 2017) so the server only observes **masked sums** of gradients or model deltas. That is a separate engineering milestone: key agreement per round, pairwise masks, dropout handling, and audited crypto libraries. Until then, document the deployment as **trusted-coordinator federated learning** and keep TLS + API keys as transport/auth controls only.

**See also:** [`FEDERATED_FULL_MPC_ROADMAP.md`](FEDERATED_FULL_MPC_ROADMAP.md) and `backend/app/services/federated_mpc_boundary.py` (interface placeholder for a future MPC engine).
