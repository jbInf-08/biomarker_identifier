## Secrets Rotation Runbook

- Scope: `SECRET_KEY`, JWT signing material, DB/Redis credentials, API keys (COSMIC/OncoKB/OpenAI), webhook secrets.
- Cadence: every 90 days (prod), immediate on suspected leak.

### Procedure

1. Create new secret versions in secret manager (AWS Secrets Manager/Azure Key Vault/GCP Secret Manager).
2. Roll out consumers in this order:
   - stateless API pods
   - workers (Celery)
   - scheduled/batch jobs
3. Keep dual-valid period where applicable:
   - JWT: accept previous key for max token TTL while issuing with new key.
   - Webhooks: allow old + new signatures during cutover window.
4. Verify:
   - `/health/ready` green in all regions.
   - auth/login and token refresh succeed.
   - background tasks + webhook delivery succeed.
5. Revoke old versions and close rotation ticket.

### Break-glass leak response

- Revoke exposed secret immediately.
- Invalidate active sessions if JWT key leaked.
- Rotate dependent upstream credentials.
- Run incident postmortem and add preventive controls.
