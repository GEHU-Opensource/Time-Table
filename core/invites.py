import hashlib
import secrets

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from core.audit import audit
from core.models import User


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def invite_link(user, token):
    return f"https://{user.tenant.slug}.{settings.BASE_DOMAIN}/invite/{token}/"


def issue_token(user):
    token = secrets.token_urlsafe(32)
    user.invite_token_hash = hash_token(token)
    user.invite_expires_at = timezone.now() + settings.INVITE_TTL
    user.save(update_fields=["invite_token_hash", "invite_expires_at"])
    return invite_link(user, token)


def send_invite_email(user, link):
    context = {
        "name": user.name,
        "tenant": user.tenant,
        "link": link,
        "hours": int(settings.INVITE_TTL.total_seconds() // 3600),
    }
    message = EmailMultiAlternatives(
        f"You are invited to {user.tenant.name} on Time-Table",
        render_to_string("email/invite.txt.pug", context),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )
    message.attach_alternative(render_to_string("email/invite.pug", context), "text/html")
    message.send()


def invite_user(actor, *, email, name, role, department=None, deliver=send_invite_email):
    user = User.objects.create_user(email, name, role=role, department=department)
    link = issue_token(user)
    deliver(user, link)
    audit(
        actor,
        "user.invited",
        user,
        after={"email": user.email, "role": role.name if role else ""},
    )
    return user


def resend_invite(actor, user, deliver=send_invite_email):
    link = issue_token(user)
    deliver(user, link)
    audit(actor, "user.invite_resent", user)
    return user


def user_for_hash(token_hash):
    if not token_hash:
        return None
    return (
        User.objects.filter(
            invite_token_hash=token_hash,
            invite_expires_at__gt=timezone.now(),
            is_active=True,
        )
        .select_related("tenant", "role")
        .first()
    )


def accept_invite(token):
    return user_for_hash(hash_token(token))


def claim_invite(user, token_hash):
    if not token_hash:
        return False
    claimed = User.objects.filter(
        pk=user.pk, invite_token_hash=token_hash, invite_expires_at__gt=timezone.now()
    ).update(invite_token_hash="", invite_expires_at=None)
    return claimed == 1


def activate(user, token_hash, password):
    if not claim_invite(user, token_hash):
        return False
    user.invite_token_hash = ""
    user.invite_expires_at = None
    user.set_password(password)
    user.auth_version += 1
    user.save(update_fields=["password", "auth_version", "invite_token_hash", "invite_expires_at"])
    audit(user, "user.activated", user)
    return True
