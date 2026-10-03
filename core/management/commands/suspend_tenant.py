from django.core.management.base import BaseCommand

from core.audit import audit
from core.management.commands.create_roles import tenant_or_error
from core.tenancy import tenant_scope


class Command(BaseCommand):
    help = "Suspend a tenant so its host answers 404, or lift the suspension"

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True)
        parser.add_argument("--unsuspend", action="store_true")

    def handle(self, *args, **options):
        tenant = tenant_or_error(options["tenant"])
        archived = not options["unsuspend"]
        with tenant_scope(tenant.id):
            before = tenant.archived
            tenant.archived = archived
            tenant.save(update_fields=["archived"])
            audit(
                None,
                "tenant.suspended" if archived else "tenant.unsuspended",
                tenant,
                before={"archived": before},
                after={"archived": archived},
            )
        state = "suspended" if archived else "active"
        self.stdout.write(f"tenant {tenant.slug} is now {state}")
