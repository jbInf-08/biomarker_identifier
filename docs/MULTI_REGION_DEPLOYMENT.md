# Multi-region production deployment

This document turns **`DEPLOYMENT_REGION`** (surfaced on `/health/live` and `/api/status`) into an operational pattern: traffic routing, data proximity, and failure isolation.

## Goals

- **Latency**: Route users to the nearest API region.
- **Availability**: Survive a single region outage for read-heavy traffic.
- **Compliance**: Keep PHI / regulated data in approved regions (configure per deployment).

## DNS and traffic

1. **Route 53** (or Cloudflare / Azure Front Door): latency-based or geolocation records pointing each region’s load balancer.
2. **Health checks**: Use `/health/live` (liveness) and `/health/ready` (readiness) from **outside** the cluster so failed regions are drained.
3. **Sticky sessions**: Prefer **stateless** API + JWT; avoid sticky LB unless required for WebSockets (then use regional WS endpoints or a dedicated gateway).

## Application configuration

- Set **`DEPLOYMENT_REGION`** per replica (e.g. `us-east-1`, `eu-west-1`).
- Clients and logs can include `region` from health/status for debugging.
- **CORS**: list every regional frontend origin in `ALLOWED_ORIGINS`.

## Data layer

- **PostgreSQL**: one writer per “home” region; **read replicas** in other regions for reporting only. The biomarker API is **write-heavy** on runs—avoid cross-region writes on the hot path unless using a global database product you trust for your SLA.
- **Redis / Celery**: run **one Redis per region** (or global Redis with careful latency). Queue names can be suffixed with region (`celery-us-east-1`) so workers never dequeue cross-region jobs by mistake.
- **Object storage (S3 / GCS / Azure Blob)**: use **same-region** buckets for uploads; replicate to a secondary region for DR if required.

## Federated learning

- Participants should call the **coordination endpoint in their jurisdiction** if policy requires it; DNS can split `federated.example.com` by geo.

## Checklist

- [ ] Regional `DEPLOYMENT_REGION` set on all pods
- [ ] Health checks wired to DNS / LB
- [ ] DB failover and backup tested (RPO/RTO)
- [ ] Secrets per region (no shared prod DB URL in plain text)
- [ ] Webhook URLs (`/api/v1/integrations/webhooks`) reachable from each region’s egress IPs if subscribers allowlist

## Related

- [`deployment/README.md`](../deployment/README.md) — short index to root compose files and deployment guides
- `docker-compose.spark.yml` for batch-heavy workloads in a **single** region unless you operate Spark federation separately
