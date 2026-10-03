from django.core.management.base import BaseCommand, CommandError

from core import invites
from core.management.commands.create_roles import ensure_roles, tenant_or_error
from core.models import User
from core.tenancy import tenant_scope


class Command(BaseCommand):
    help = "Invite the first Admin of a tenant"

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True)
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument("--print-link", action="store_true", dest="print_link")

    def handle(self, *args, **options):
        tenant = tenant_or_error(options["tenant"])
        email = options["email"].lower()
        with tenant_scope(tenant.id):
            if User.objects.filter(email=email).exists():
                raise CommandError("a user with that email already exists in this tenant")
            roles = ensure_roles()
            deliver = self.print_link if options["print_link"] else invites.send_invite_email
            user = invites.invite_user(
                None, email=email, name=options["name"], role=roles["Admin"], deliver=deliver
            )
        self.stdout.write(f"invited admin {user.id} for tenant {tenant.slug}")

    def print_link(self, user, link):
        self.stdout.write(link)
