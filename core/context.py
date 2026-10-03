def perms(request):
    user = getattr(request, "user", None)
    tenant = getattr(request, "tenant", None)
    return {
        "perms": user.perms if user is not None and user.is_authenticated else frozenset(),
        "tenant": tenant,
    }
