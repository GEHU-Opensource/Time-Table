from django.db import migrations

ROLES = """
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tt_app') THEN
    CREATE ROLE tt_app NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tt_worker') THEN
    CREATE ROLE tt_worker NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tt_ops') THEN
    CREATE ROLE tt_ops NOLOGIN;
  END IF;
END $$;
"""

GRANTS = """
DO $$
BEGIN
  EXECUTE 'GRANT USAGE ON SCHEMA public TO tt_app, tt_worker, tt_ops';
EXCEPTION WHEN insufficient_privilege THEN
  NULL;
END $$;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO tt_app, tt_worker;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO tt_app, tt_worker;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO tt_ops;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO tt_app, tt_worker;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO tt_app, tt_worker;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO tt_ops;
"""

FUNCTIONS = """
CREATE OR REPLACE FUNCTION app_tenant_id() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app.tenant_id', true), '')::uuid
$$;

CREATE OR REPLACE FUNCTION forbid_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'rows of % are append only', TG_TABLE_NAME
    USING ERRCODE = 'integrity_constraint_violation';
END $$;
"""

TENANT_TABLE = """
ALTER TABLE core_tenant ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_read ON core_tenant FOR SELECT USING (true);
CREATE POLICY tenant_update ON core_tenant FOR UPDATE
  USING (id = app_tenant_id()) WITH CHECK (id = app_tenant_id());
"""

TABLES = ["core_department", "core_role", "core_user", "core_auditevent"]

RLS = """
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_rw ON {table}
  USING (tenant_id = app_tenant_id()) WITH CHECK (tenant_id = app_tenant_id());
CREATE POLICY ops_read ON {table} FOR SELECT TO tt_ops USING (true);
"""

COMPOSITE_FKS = """
ALTER TABLE core_user ADD CONSTRAINT core_user_role_same_tenant
  FOREIGN KEY (tenant_id, role_id) REFERENCES core_role (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE core_user ADD CONSTRAINT core_user_department_same_tenant
  FOREIGN KEY (tenant_id, department_id) REFERENCES core_department (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE core_auditevent ADD CONSTRAINT core_auditevent_actor_same_tenant
  FOREIGN KEY (tenant_id, actor_id) REFERENCES core_user (tenant_id, id)
  DEFERRABLE INITIALLY DEFERRED;
"""

AUDIT = """
REVOKE UPDATE, DELETE ON core_auditevent FROM tt_app, tt_worker;
CREATE TRIGGER core_auditevent_append_only
  BEFORE UPDATE OR DELETE ON core_auditevent
  FOR EACH ROW EXECUTE FUNCTION forbid_change();
"""

OTP = """
ALTER TABLE otp_totp_totpdevice ENABLE ROW LEVEL SECURITY;
ALTER TABLE otp_totp_totpdevice FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_user ON otp_totp_totpdevice
  USING (user_id IN (SELECT id FROM core_user))
  WITH CHECK (user_id IN (SELECT id FROM core_user));
CREATE POLICY ops_read ON otp_totp_totpdevice FOR SELECT TO tt_ops USING (true);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("otp_totp", "0003_add_timestamps"),
    ]

    operations = [
        migrations.RunSQL(ROLES, migrations.RunSQL.noop),
        migrations.RunSQL(GRANTS, migrations.RunSQL.noop),
        migrations.RunSQL(FUNCTIONS, migrations.RunSQL.noop),
        migrations.RunSQL(TENANT_TABLE, migrations.RunSQL.noop),
        *[migrations.RunSQL(RLS.format(table=table), migrations.RunSQL.noop) for table in TABLES],
        migrations.RunSQL(COMPOSITE_FKS, migrations.RunSQL.noop),
        migrations.RunSQL(AUDIT, migrations.RunSQL.noop),
        migrations.RunSQL(OTP, migrations.RunSQL.noop),
    ]
