from django.utils import timezone
from procrastinate.contrib.django import app

from core.models import Tenant
from core.tenancy import tenant_scope

EVERY_FIVE_MINUTES = "*/5 * * * *"


def live_tenant_ids():
    return list(Tenant.objects.filter(archived=False).values_list("id", flat=True))


@app.task(name="timetable.solve_version", retry=False)
def solve_version(version_id, tenant_id):
    from timetable import services

    services.run_solve(version_id, tenant_id)


@app.periodic(cron=EVERY_FIVE_MINUTES)
@app.task(name="timetable.flip_live_all", retry=False)
def flip_live_all(timestamp):
    from timetable import services

    on = timezone.localdate()
    for tenant_id in live_tenant_ids():
        with tenant_scope(tenant_id):
            services.flip_live(on)


@app.periodic(cron=EVERY_FIVE_MINUTES)
@app.task(name="timetable.reset_stale_all", retry=False)
def reset_stale_all(timestamp):
    from timetable import services

    now = timezone.now()
    for tenant_id in live_tenant_ids():
        with tenant_scope(tenant_id):
            services.reset_stale_solving(now)
