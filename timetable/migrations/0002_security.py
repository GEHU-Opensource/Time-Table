from django.db import migrations

TABLES = [
    "timetable_resource",
    "timetable_subject",
    "timetable_timetable",
    "timetable_version",
    "timetable_requirement",
    "timetable_requirementresource",
    "timetable_assignment",
]

RLS = """
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_rw ON {table}
  USING (tenant_id = app_tenant_id()) WITH CHECK (tenant_id = app_tenant_id());
CREATE POLICY ops_read ON {table} FOR SELECT TO tt_ops USING (true);
"""

COMPOSITE_FKS = """
ALTER TABLE timetable_resource ADD CONSTRAINT timetable_resource_department_same_tenant
  FOREIGN KEY (tenant_id, department_id) REFERENCES core_department (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE timetable_resource ADD CONSTRAINT timetable_resource_parent_same_tenant
  FOREIGN KEY (tenant_id, parent_id) REFERENCES timetable_resource (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE timetable_resource ADD CONSTRAINT timetable_resource_user_same_tenant
  FOREIGN KEY (tenant_id, user_id) REFERENCES core_user (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE timetable_subject ADD CONSTRAINT timetable_subject_department_same_tenant
  FOREIGN KEY (tenant_id, department_id) REFERENCES core_department (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE timetable_timetable ADD CONSTRAINT timetable_timetable_department_same_tenant
  FOREIGN KEY (tenant_id, department_id) REFERENCES core_department (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE timetable_version ADD CONSTRAINT timetable_version_timetable_same_tenant
  FOREIGN KEY (tenant_id, timetable_id) REFERENCES timetable_timetable (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE timetable_version ADD CONSTRAINT timetable_version_parent_same_tenant
  FOREIGN KEY (tenant_id, parent_id) REFERENCES timetable_version (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE timetable_version ADD CONSTRAINT timetable_version_creator_same_tenant
  FOREIGN KEY (tenant_id, created_by_id) REFERENCES core_user (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE timetable_requirement ADD CONSTRAINT timetable_requirement_version_same_tenant
  FOREIGN KEY (tenant_id, version_id) REFERENCES timetable_version (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE timetable_requirement ADD CONSTRAINT timetable_requirement_subject_same_tenant
  FOREIGN KEY (tenant_id, subject_id) REFERENCES timetable_subject (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE timetable_requirementresource ADD CONSTRAINT timetable_rr_requirement_same_tenant
  FOREIGN KEY (tenant_id, requirement_id) REFERENCES timetable_requirement (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE timetable_requirementresource ADD CONSTRAINT timetable_rr_resource_same_tenant
  FOREIGN KEY (tenant_id, resource_id) REFERENCES timetable_resource (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE timetable_assignment ADD CONSTRAINT timetable_assignment_version_same_tenant
  FOREIGN KEY (tenant_id, version_id) REFERENCES timetable_version (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE timetable_assignment ADD CONSTRAINT timetable_assignment_requirement_same_tenant
  FOREIGN KEY (tenant_id, requirement_id) REFERENCES timetable_requirement (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE timetable_assignment ADD CONSTRAINT timetable_assignment_resource_same_tenant
  FOREIGN KEY (tenant_id, resource_id) REFERENCES timetable_resource (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE timetable_assignment ADD CONSTRAINT timetable_assignment_serves_same_tenant
  FOREIGN KEY (tenant_id, serves_id) REFERENCES timetable_resource (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
"""

GUARDS = """
CREATE OR REPLACE FUNCTION version_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'published' THEN
    IF NEW IS DISTINCT FROM OLD THEN
      RAISE EXCEPTION 'published versions are immutable'
        USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
  END IF;
  IF NEW.status IS DISTINCT FROM OLD.status AND NOT (
       (OLD.status = 'draft' AND NEW.status IN ('solving', 'published'))
    OR (OLD.status = 'solving' AND NEW.status IN ('draft', 'failed'))
    OR (OLD.status = 'failed' AND NEW.status IN ('draft', 'solving'))
  ) THEN
    RAISE EXCEPTION 'illegal version transition % -> %', OLD.status, NEW.status
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  IF NEW.status = 'published' AND NEW.effective_from IS NULL THEN
    RAISE EXCEPTION 'published versions need effective_from'
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION requirement_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_status text;
BEGIN
  SELECT status INTO v_status FROM timetable_version
    WHERE id = COALESCE(NEW.version_id, OLD.version_id);
  IF v_status IS NULL OR v_status NOT IN ('draft', 'failed') THEN
    RAISE EXCEPTION 'requirements of a % version are frozen', COALESCE(v_status, 'hidden')
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN COALESCE(NEW, OLD);
END $$;

CREATE OR REPLACE FUNCTION requirement_resource_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_status text;
BEGIN
  SELECT v.status INTO v_status
    FROM timetable_requirement r JOIN timetable_version v ON v.id = r.version_id
    WHERE r.id = COALESCE(NEW.requirement_id, OLD.requirement_id);
  IF v_status IS NULL OR v_status NOT IN ('draft', 'failed') THEN
    RAISE EXCEPTION 'participants of a % version are frozen', COALESCE(v_status, 'hidden')
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN COALESCE(NEW, OLD);
END $$;

CREATE OR REPLACE FUNCTION assignment_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_status text;
BEGIN
  SELECT status INTO v_status FROM timetable_version
    WHERE id = COALESCE(NEW.version_id, OLD.version_id);
  IF v_status IS NULL THEN
    RAISE EXCEPTION 'version not visible' USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  IF TG_OP = 'INSERT' THEN
    IF v_status NOT IN ('draft', 'solving') OR NEW.is_live THEN
      RAISE EXCEPTION 'cannot add assignments to a % version', v_status
        USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
  END IF;
  IF TG_OP = 'DELETE' THEN
    IF v_status NOT IN ('draft', 'solving', 'failed') THEN
      RAISE EXCEPTION 'assignments of a % version cannot be deleted', v_status
        USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN OLD;
  END IF;
  IF NEW.is_live AND v_status <> 'published' THEN
    RAISE EXCEPTION 'only published assignments can be live'
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  IF v_status = 'published' AND ROW(NEW.version_id, NEW.requirement_id, NEW.session,
       NEW.resource_id, NEW.day, NEW.period, NEW.serves_id, NEW.tenant_id)
     IS DISTINCT FROM ROW(OLD.version_id, OLD.requirement_id, OLD.session,
       OLD.resource_id, OLD.day, OLD.period, OLD.serves_id, OLD.tenant_id) THEN
    RAISE EXCEPTION 'published assignments are immutable except is_live'
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER timetable_version_guard BEFORE UPDATE ON timetable_version
  FOR EACH ROW EXECUTE FUNCTION version_guard();
CREATE TRIGGER timetable_version_no_delete BEFORE DELETE ON timetable_version
  FOR EACH ROW EXECUTE FUNCTION forbid_change();
CREATE TRIGGER timetable_timetable_no_delete BEFORE DELETE ON timetable_timetable
  FOR EACH ROW EXECUTE FUNCTION forbid_change();
CREATE TRIGGER timetable_requirement_guard
  BEFORE INSERT OR UPDATE OR DELETE ON timetable_requirement
  FOR EACH ROW EXECUTE FUNCTION requirement_guard();
CREATE TRIGGER timetable_requirement_resource_guard
  BEFORE INSERT OR UPDATE OR DELETE ON timetable_requirementresource
  FOR EACH ROW EXECUTE FUNCTION requirement_resource_guard();
CREATE TRIGGER timetable_assignment_guard
  BEFORE INSERT OR UPDATE OR DELETE ON timetable_assignment
  FOR EACH ROW EXECUTE FUNCTION assignment_guard();

REVOKE DELETE ON timetable_version, timetable_timetable, timetable_resource, timetable_subject
  FROM tt_app, tt_worker;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("timetable", "0001_initial"),
        ("core", "0002_security"),
    ]

    operations = [
        *[migrations.RunSQL(RLS.format(table=table), migrations.RunSQL.noop) for table in TABLES],
        migrations.RunSQL(COMPOSITE_FKS, migrations.RunSQL.noop),
        migrations.RunSQL(GUARDS, migrations.RunSQL.noop),
    ]
