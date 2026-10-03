from django.core.management.base import BaseCommand, CommandError

from core.audit import audit
from core.models import Role, Tenant
from core.perms import ROLE_PRESETS
from core.tenancy import tenant_scope


def tenant_or_error(slug):
    tenant = Tenant.objects.filter(slug=slug).first()
    if tenant is None:
        raise CommandError(f"no tenant with slug {slug!r}")
    return tenant


def ensure_roles(actor=None):
    roles = {}
    for name, preset in ROLE_PRESETS.items():
        role, created = Role.objects.get_or_create(
            name=name, defaults={"permissions": list(preset)}
        )
        if created:
            audit(
                actor, "role.created", role, after={"name": name, "permissions": role.permissions}
            )
        else:
            merged = sorted(set(role.permissions) | set(preset))
            if merged != sorted(role.permissions):
                before = list(role.permissions)
                role.permissions = merged
                role.save(update_fields=["permissions"])
                audit(
                    actor,
                    "role.updated",
                    role,
                    before={"permissions": before},
                    after={"permissions": merged},
                )
        roles[name] = role
    return roles


class Command(BaseCommand):
    help = "Ensure the preset roles exist for a tenant without removing any permission"

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True)

    def handle(self, *args, **options):
        tenant = tenant_or_error(options["tenant"])
        with tenant_scope(tenant.id):
            roles = ensure_roles()
        self.stdout.write(f"{tenant.slug}: {', '.join(sorted(roles))}")
