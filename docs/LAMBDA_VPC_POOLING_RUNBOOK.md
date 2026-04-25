## Lambda / Serverless Production Notes

This complements `deployment/serverless/template.yaml`.

- Package strategy:
  - keep function zip small (< 50MB compressed)
  - move heavy deps (numpy/scipy/pandas) to Lambda layers or container image deployment
- VPC:
  - place Lambda in private subnets when DB/Redis are private
  - add NAT or VPC endpoints for required egress
- DB + Redis pooling:
  - use low SQLAlchemy pool sizes for Lambda burst (`DB_POOL_SIZE=1`, low overflow)
  - prefer RDS Proxy / PgBouncer for PostgreSQL
  - for Redis, reuse client objects across invocations and set short timeouts
- Cold starts:
  - minimize import-time work
  - keep optional heavy modules lazy-loaded
  - use provisioned concurrency for latency-sensitive APIs

### Validation checklist

- `sam validate` and `sam build` succeed
- p95 latency measured under warm and cold paths
- DB connection count remains stable under burst tests
- timeout/retry policy tested for downstream failures
