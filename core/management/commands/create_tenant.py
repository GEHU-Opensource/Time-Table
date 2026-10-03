from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from core.audit import audit
from core.management.commands.create_roles import ensure_roles
from core.models import Tenant
from core.tenancy import tenant_scope


class Command(BaseCommand):
    help = "Create a tenant with its preset roles"

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--slug", required=True)

    def handle(self, *args, **options):
        slug = options["slug"].lower()
        if slugify(slug) != slug or "." in slug:
            raise CommandError("slug must be lowercase letters, digits and hyphens")
        if Tenant.objects.filter(slug=slug).exists():
            raise CommandError(f"tenant {slug!r} already exists")
        tenant = Tenant.objects.create(name=options["name"], slug=slug)
        with tenant_scope(tenant.id):
            audit(None, "tenant.created", tenant, after={"slug": slug})
            ensure_roles()
        self.stdout.write(f"created tenant {tenant.slug} ({tenant.id})")
