from django.db import migrations

VERSION_GUARD = """
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
       (OLD.status = 'draft' AND NEW.status IN ('solving', 'published', 'failed'))
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
"""


class Migration(migrations.Migration):
    dependencies = [
        ("timetable", "0002_security"),
    ]

    operations = [
        migrations.RunSQL(VERSION_GUARD, migrations.RunSQL.noop),
    ]
