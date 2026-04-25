## Compliance Checklist Workflow

Operational workflow for IRB/HIPAA/GDPR controls using API-backed checklist items.

### Endpoints

- `POST /api/v1/admin/compliance/checklist-items` (admin)
- `GET /api/v1/admin/compliance/checklist-items` (tenant-scoped)
- `PATCH /api/v1/admin/compliance/checklist-items/{item_id}` (status changes admin-only)

### Status evidence rules (required before commit)

The API validates the **combined** row after a `PATCH` (merged updates + existing fields):

| Status | Required evidence |
| --- | --- |
| `open` | None |
| `in_progress` | None (optional `evidence_link` / `notes`) |
| `complete` | Non-empty `evidence_link` (URL, ticket ID, or document locator). Plain `notes` alone do **not** satisfy completion. |
| `waived` | `notes` with at least **20 characters** describing waiver rationale, scope limits, and approver context. |

Failed validation returns `400` with an explicit `detail` string suitable for audit logs and UI copy.

### Lifecycle

1. Create item with `framework`, `control_code`, `title`, `tenant_id`, optional `due_date`.
2. Assign owner and attach evidence links as implementation progresses.
3. Move status: `open -> in_progress -> complete` (or `waived` with documented rationale).
4. Export periodic snapshot for audit package and deployment readiness gates.

### Auditability

- Changes are recorded in `audit_logs` via `log_audit`.
- Checklist rows are stored in `compliance_checklist_items`.
- Tenant filtering applies automatically for non-admin users.

### Database isolation (optional)

For PostgreSQL deployments, row-level security policies and operator guidance live in `docs/POSTGRES_ROW_LEVEL_SECURITY.md` and `ops/postgres/rls_policies.sql` (defense-in-depth; not a substitute for API tenant checks).
