## IRB, HIPAA, and GDPR Operational Policy Notes

This file is a technical-policy bridge, not legal advice.

### IRB / Human subjects

- Any non-public human-subjects research requires IRB determination/approval before ingestion.
- Track protocol ID and consent constraints per dataset.
- Restrict analysis access by role and tenant.

### HIPAA (US)

- Treat PHI as high-risk: encrypt in transit and at rest.
- Enforce least privilege and auditable access logs.
- Maintain BAAs with covered entities/cloud vendors where applicable.
- Implement breach response workflows and retention policies.

### GDPR (EU)

- Define lawful basis for processing and purpose limitation.
- Implement data minimization and retention/deletion schedules.
- Support data subject rights workflows (access/erasure/export requests).
- Keep regional data residency controls where required.

### Required engineering controls

- Tenant isolation and RBAC (enforced in API + DB policies)
- Immutable audit logs for sensitive actions
- Secrets rotation + key management runbooks
- Multi-region DR drills with documented RTO/RPO

### Required artifacts before production with patient data

- Data flow diagram and threat model sign-off
- IRB/DUA records attached to deployment ticket
- HIPAA/GDPR control checklist and owner sign-off
