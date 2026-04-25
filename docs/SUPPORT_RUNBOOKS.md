## Support Runbooks & Ticketing Procedures

This file describes a generic support model and ties into the operations docs in
this repository. For environment-specific playbooks, see
[OPERATIONS_AND_RUNBOOKS.md](OPERATIONS_AND_RUNBOOKS.md).

### 1. Support Model

- **Tier 1**: Help desk and basic usage questions.
- **Tier 2**: Application support (bug triage, configuration issues).
- **Tier 3**: Engineering/DevOps for code or infrastructure changes.

### 2. Standard Incident Flow

1. Ticket created in the chosen system (e.g., JIRA, ServiceNow, GitHub Issues).
2. Tier 1 reviews, classifies severity, and gathers logs / screenshots.
3. If needed, escalate to Tier 2/3 with:
   - Steps to reproduce
   - Logs or relevant monitoring screenshots
   - Impact assessment (users/tenants affected, workflows blocked)

### 3. Common Runbooks

- **Pipeline Failure**
  - Check recent runs and logs.
  - Consult `OPERATIONS_AND_RUNBOOKS.md` for recovery steps.
  - Re‑run failed analyses after fix and confirm with requestor.
- **Performance Degradation**
  - Inspect dashboards in Grafana and recent deployments.
  - Validate database and cache health.
  - Initiate mitigation (roll back, scale out) according to ops guide.
- **Data/Result Issues**
  - Verify input formats and recent configuration changes.
  - Compare behavior in staging vs. production when possible.

### 4. Ticket Quality Checklist

- Clear summary and severity.
- Reproduction steps and expected vs actual behavior.
- Environment details (tenant, run ID, browser, etc.).
- Links to related dashboards or logs when relevant.

For more detailed operational guidance, see `SYSTEM_ADMINISTRATION_GUIDE.md`
and `OPERATIONS_AND_RUNBOOKS.md`.

