import hashlib

from core.models import AuditEvent
from core.tenancy import request_id

HASHED_FIELDS = frozenset({"email", "name", "password", "invite_token_hash"})


def digest(value):
    return hashlib.sha256(str(value).encode()).hexdigest()[:16]


def scrub(data):
    return {
        key: digest(value) if key in HASHED_FIELDS else value for key, value in (data or {}).items()
    }


def audit(actor, action, obj=None, before=None, after=None):
    return AuditEvent.objects.create(
        actor=actor if actor is not None and actor.is_authenticated else None,
        action=action,
        object_type=type(obj).__name__ if obj is not None else "",
        object_id=getattr(obj, "pk", None),
        before=scrub(before),
        after=scrub(after),
        request_id=request_id.get(),
    )
