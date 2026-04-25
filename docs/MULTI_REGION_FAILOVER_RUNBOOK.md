## Multi-region Failover Drill Runbook

Use with `docs/MULTI_REGION_DEPLOYMENT.md`.

### Quarterly drill

1. Pick primary + secondary regions and announce maintenance window.
2. Freeze schema changes and verify backups.
3. Simulate primary API failure (drain LB / fail readiness).
4. Confirm traffic shifts to secondary region.
5. Validate critical paths:
   - auth/login
   - run creation/status
   - webhook dispatch
6. Validate data plane:
   - DB replica promotion or write strategy works
   - Redis/Celery regional queues process jobs
7. Recover primary and rebalance traffic.
8. Record RTO/RPO, user impact, and corrective actions.

### Alert thresholds

- failover trigger if regional 5xx > 5% for 5 minutes
- trigger if `/health/ready` down > 2 minutes
