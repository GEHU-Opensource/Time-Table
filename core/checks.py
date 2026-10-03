from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def production_settings(app_configs, **kwargs):
    errors = []
    if settings.ENV == "prod" and settings.DEBUG:
        errors.append(Error("DEBUG is on in prod", id="core.E001"))
    if settings.ENV == "prod" and not settings.SECURE:
        errors.append(Error("SECURE is off in prod", id="core.E002"))
    if len(settings.SECRET_KEY) < 50:
        errors.append(Error("SECRET_KEY is shorter than 50 characters", id="core.E003"))
    return errors
