# PostgreSQL row-level security (RLS)

This document explains how to add **defense-in-depth** tenant isolation at the database layer for deployments that use PostgreSQL. Application-level checks (`apply_tenant_scope`, headers) remain mandatory; RLS limits damage if a query path forgets a filter or a connection is misused.

## Prerequisites

- PostgreSQL 12+ (tested patterns use `current_setting(..., true)`).
- Application DB user must **not** be a superuser. Prefer a dedicated role (e.g. `biomarker_app`) with `NOBYPASSRLS`.
- Decide how each **connection** will establish context before queries run (see below).

## Session context: `app.tenant_id`

Policies in `ops/postgres/rls_policies.sql` assume a per-transaction GUC:

```sql
SET LOCAL app.tenant_id = 'uuid-of-tenant';
```

- Use **`SET LOCAL`** so the value clears at transaction end (safe for pooled connections).
- The API should set this from the same source of truth as `X-Tenant-ID` / JWT tenant claims **after** authentication and tenant resolution.
- **Workers** (Celery, cron): set `SET LOCAL app.tenant_id` at the start of each job from the job payload, or use a separate DB role with `BYPASSRLS` only where cross-tenant maintenance is required (document who may use it).

### Optional bypass (break-glass / migrations only)

Scripts define `app.rls_bypass`. When set to the literal `true`, policies allow all rows **for that transaction**. Grant the ability to set this GUC only to a migration/admin role, never the pooled app user.

```sql
SET LOCAL app.rls_bypass = 'true';
-- run migration / one-off admin query
```

## Connection pooling

- **PgBouncer** transaction pooling: `SET LOCAL` is valid for the transaction; ensure your ORM issues explicit `BEGIN` and sets GUCs inside the same transaction as business queries.
- **Session pooling**: you may use session-level `SET app.tenant_id` instead; ensure idle sessions reset tenant context before reuse.
- **SQLAlchemy**: a common pattern is `before_cursor_execute` or opening the session with a listener that runs `SET LOCAL` once per request transaction—keep it aligned with FastAPI dependency scope.

## Policy semantics (strict mode)

The shipped SQL uses **strict** visibility when `app.rls_bypass` is not `true`:

- Rows with `tenant_id IS NULL` remain visible (legacy / global rows).
- Rows with a non-null `tenant_id` are visible only if `app.tenant_id` is set and matches.

Implications:

- **Cross-tenant admin dashboards** cannot rely on the same pooled role unless they use a **bypass** connection, a **separate service role** with `BYPASSRLS`, or per-request tenant scoping with multiple round-trips.
- **Unit tests** on SQLite ignore this file; CI against Postgres should run the SQL in a staging schema after review.

## Tables covered

| Table | Column / rule |
| --- | --- |
| `analysis_runs` | `tenant_id` |
| `biomarker_results` | Inherited via `EXISTS` join to `analysis_runs` |
| `research_projects` | `tenant_id` |
| `project_members` | Inherited via `research_projects` |
| `spark_jobs` | `tenant_id` |
| `compliance_checklist_items` | `tenant_id` |

Other tables (e.g. `users`, `webhook_subscriptions`) need separate policies if you extend RLS—often keyed on `user_id` with `app.user_id` GUC.

## Applying policies

1. Review and adapt `ops/postgres/rls_policies.sql` for your schema names and roles.
2. Apply in a maintenance window on a staging clone first.
3. Enable `FORCE ROW LEVEL SECURITY` only after verifying the app sets `app.tenant_id` (or uses an approved bypass role) for every code path.

## Rollback

Disable RLS (example for one table):

```sql
ALTER TABLE analysis_runs NO FORCE ROW LEVEL SECURITY;
ALTER TABLE analysis_runs DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS analysis_runs_tenant_isolation ON analysis_runs;
```

Repeat per table/policy names from the ops script.

## Compliance note

RLS supports audit narratives (“database enforces tenant boundary”) but must be paired with evidence: migration tickets, role grants, and proof that production app users cannot set `app.rls_bypass`. Application-level control evidence is described in `docs/COMPLIANCE_CHECKLIST_WORKFLOW.md`.
