-- Row-level security policies (PostgreSQL).
-- Review docs/POSTGRES_ROW_LEVEL_SECURITY.md before applying.
-- Idempotent-ish: drops named policies then recreates. Run in a transaction after backup.

BEGIN;

-- --- analysis_runs ----------------------------------------------------------
ALTER TABLE analysis_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_runs FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS analysis_runs_tenant_isolation ON analysis_runs;
CREATE POLICY analysis_runs_tenant_isolation ON analysis_runs
  FOR ALL
  USING (
    COALESCE(current_setting('app.rls_bypass', true), '') = 'true'
    OR tenant_id IS NULL
    OR (
      current_setting('app.tenant_id', true) IS NOT NULL
      AND tenant_id::text = current_setting('app.tenant_id', true)
    )
  )
  WITH CHECK (
    COALESCE(current_setting('app.rls_bypass', true), '') = 'true'
    OR tenant_id IS NULL
    OR (
      current_setting('app.tenant_id', true) IS NOT NULL
      AND tenant_id::text = current_setting('app.tenant_id', true)
    )
  );

-- --- biomarker_results (tenant via parent run) ----------------------------
ALTER TABLE biomarker_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE biomarker_results FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS biomarker_results_tenant_isolation ON biomarker_results;
CREATE POLICY biomarker_results_tenant_isolation ON biomarker_results
  FOR ALL
  USING (
    COALESCE(current_setting('app.rls_bypass', true), '') = 'true'
    OR EXISTS (
      SELECT 1
      FROM analysis_runs ar
      WHERE ar.id = biomarker_results.run_id
        AND (
          ar.tenant_id IS NULL
          OR (
            current_setting('app.tenant_id', true) IS NOT NULL
            AND ar.tenant_id::text = current_setting('app.tenant_id', true)
          )
        )
    )
  )
  WITH CHECK (
    COALESCE(current_setting('app.rls_bypass', true), '') = 'true'
    OR EXISTS (
      SELECT 1
      FROM analysis_runs ar
      WHERE ar.id = biomarker_results.run_id
        AND (
          ar.tenant_id IS NULL
          OR (
            current_setting('app.tenant_id', true) IS NOT NULL
            AND ar.tenant_id::text = current_setting('app.tenant_id', true)
          )
        )
    )
  );

-- --- research_projects ------------------------------------------------------
ALTER TABLE research_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_projects FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS research_projects_tenant_isolation ON research_projects;
CREATE POLICY research_projects_tenant_isolation ON research_projects
  FOR ALL
  USING (
    COALESCE(current_setting('app.rls_bypass', true), '') = 'true'
    OR tenant_id IS NULL
    OR (
      current_setting('app.tenant_id', true) IS NOT NULL
      AND tenant_id::text = current_setting('app.tenant_id', true)
    )
  )
  WITH CHECK (
    COALESCE(current_setting('app.rls_bypass', true), '') = 'true'
    OR tenant_id IS NULL
    OR (
      current_setting('app.tenant_id', true) IS NOT NULL
      AND tenant_id::text = current_setting('app.tenant_id', true)
    )
  );

-- --- project_members (tenant via project) ---------------------------------
ALTER TABLE project_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_members FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS project_members_tenant_isolation ON project_members;
CREATE POLICY project_members_tenant_isolation ON project_members
  FOR ALL
  USING (
    COALESCE(current_setting('app.rls_bypass', true), '') = 'true'
    OR EXISTS (
      SELECT 1
      FROM research_projects rp
      WHERE rp.id = project_members.project_id
        AND (
          rp.tenant_id IS NULL
          OR (
            current_setting('app.tenant_id', true) IS NOT NULL
            AND rp.tenant_id::text = current_setting('app.tenant_id', true)
          )
        )
    )
  )
  WITH CHECK (
    COALESCE(current_setting('app.rls_bypass', true), '') = 'true'
    OR EXISTS (
      SELECT 1
      FROM research_projects rp
      WHERE rp.id = project_members.project_id
        AND (
          rp.tenant_id IS NULL
          OR (
            current_setting('app.tenant_id', true) IS NOT NULL
            AND rp.tenant_id::text = current_setting('app.tenant_id', true)
          )
        )
    )
  );

-- --- spark_jobs -------------------------------------------------------------
ALTER TABLE spark_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE spark_jobs FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS spark_jobs_tenant_isolation ON spark_jobs;
CREATE POLICY spark_jobs_tenant_isolation ON spark_jobs
  FOR ALL
  USING (
    COALESCE(current_setting('app.rls_bypass', true), '') = 'true'
    OR tenant_id IS NULL
    OR (
      current_setting('app.tenant_id', true) IS NOT NULL
      AND tenant_id::text = current_setting('app.tenant_id', true)
    )
  )
  WITH CHECK (
    COALESCE(current_setting('app.rls_bypass', true), '') = 'true'
    OR tenant_id IS NULL
    OR (
      current_setting('app.tenant_id', true) IS NOT NULL
      AND tenant_id::text = current_setting('app.tenant_id', true)
    )
  );

-- --- compliance_checklist_items -------------------------------------------
ALTER TABLE compliance_checklist_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance_checklist_items FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS compliance_checklist_items_tenant_isolation ON compliance_checklist_items;
CREATE POLICY compliance_checklist_items_tenant_isolation ON compliance_checklist_items
  FOR ALL
  USING (
    COALESCE(current_setting('app.rls_bypass', true), '') = 'true'
    OR tenant_id IS NULL
    OR (
      current_setting('app.tenant_id', true) IS NOT NULL
      AND tenant_id::text = current_setting('app.tenant_id', true)
    )
  )
  WITH CHECK (
    COALESCE(current_setting('app.rls_bypass', true), '') = 'true'
    OR tenant_id IS NULL
    OR (
      current_setting('app.tenant_id', true) IS NOT NULL
      AND tenant_id::text = current_setting('app.tenant_id', true)
    )
  );

COMMIT;
