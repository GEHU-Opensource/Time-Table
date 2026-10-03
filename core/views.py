import base64
from io import BytesIO

import qrcode
from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django_otp import login as otp_login
from django_otp import match_token, user_has_device
from django_otp.plugins.otp_totp.models import TOTPDevice

from core import invites
from core.audit import audit
from core.auth import BACKEND_PATH
from core.forms import (
    EmailAuthenticationForm,
    NewPasswordForm,
    TenantPasswordResetForm,
    TotpTokenForm,
)

INVITE_SESSION_KEY = "invite_token_hash"
TOKEN_MISMATCH = "That code did not match. Wait for a new code and try again."
INVITE_GONE = "This invitation is no longer valid."

try:
    from qrcode.image.pil import PilImage as QrImage

    QR_MEDIA_TYPE = "image/png"
except ImportError:
    from qrcode.image.svg import SvgPathImage as QrImage

    QR_MEDIA_TYPE = "image/svg+xml"


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")


def qr_data_uri(text):
    buffer = BytesIO()
    qrcode.make(text, image_factory=QrImage, box_size=6, border=2).save(buffer)
    return f"data:{QR_MEDIA_TYPE};base64,{base64.b64encode(buffer.getvalue()).decode()}"


class LoginView(auth_views.LoginView):
    template_name = "auth/login.pug"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True
    extra_context = {"title": "Sign in"}

    def form_valid(self, form):
        response = super().form_valid(form)
        audit(self.request.user, "user.login", self.request.user)
        return response


class LogoutView(auth_views.LogoutView):
    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            audit(request.user, "user.logout", request.user)
        return super().post(request, *args, **kwargs)


class MfaSetupView(LoginRequiredMixin, View):
    template_name = "auth/mfa_setup.pug"

    def pending_device(self, user):
        device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
        if device is None:
            device = TOTPDevice.objects.create(user=user, confirmed=False, name="authenticator")
        return device

    def render_page(self, request, device, form):
        return render(
            request,
            self.template_name,
            {
                "title": "Two-factor setup",
                "form": form,
                "qr": qr_data_uri(device.config_url),
                "secret": base64.b32encode(device.bin_key).decode(),
                "enabled": user_has_device(request.user, confirmed=True),
                "required": request.user.needs_mfa,
            },
        )

    def get(self, request):
        return self.render_page(request, self.pending_device(request.user), TotpTokenForm())

    def post(self, request):
        device = self.pending_device(request.user)
        form = TotpTokenForm(request.POST)
        if form.is_valid():
            if device.verify_token(form.cleaned_data["token"]):
                device.confirmed = True
                device.save(update_fields=["confirmed"])
                TOTPDevice.objects.filter(user=request.user, confirmed=False).delete()
                otp_login(request, device)
                audit(request.user, "mfa.enabled", request.user)
                return redirect(settings.LOGIN_REDIRECT_URL)
            audit(request.user, "mfa.setup_failed", request.user)
            form.add_error("token", TOKEN_MISMATCH)
        return self.render_page(request, device, form)


class MfaVerifyView(LoginRequiredMixin, View):
    template_name = "auth/mfa_verify.pug"

    def render_page(self, request, form):
        return render(request, self.template_name, {"title": "Two-factor check", "form": form})

    def get(self, request):
        if not user_has_device(request.user, confirmed=True):
            return redirect("mfa-setup")
        return self.render_page(request, TotpTokenForm())

    def post(self, request):
        form = TotpTokenForm(request.POST)
        if form.is_valid():
            device = match_token(request.user, form.cleaned_data["token"])
            if device is not None:
                otp_login(request, device)
                audit(request.user, "mfa.verified", request.user)
                return redirect(settings.LOGIN_REDIRECT_URL)
            audit(request.user, "mfa.verify_failed", request.user)
            form.add_error("token", TOKEN_MISMATCH)
        return self.render_page(request, form)


def invite_invalid(request):
    return render(request, "auth/invite_invalid.pug", {"title": "Invitation"}, status=404)


class InviteAcceptView(View):
    def get(self, request, token):
        user = invites.accept_invite(token)
        if user is None:
            return invite_invalid(request)
        request.session[INVITE_SESSION_KEY] = invites.hash_token(token)
        return redirect("invite-set-password")


class InviteSetPasswordView(View):
    template_name = "auth/invite_set_password.pug"

    def dispatch(self, request, *args, **kwargs):
        token_hash = request.session.get(INVITE_SESSION_KEY, "")
        user = invites.user_for_hash(token_hash)
        if user is None:
            return invite_invalid(request)
        if request.method == "POST":
            return self.post(request, user, token_hash)
        return self.get(request, user)

    def render_page(self, request, user, form):
        return render(
            request,
            self.template_name,
            {"title": "Set your password", "form": form, "invited": user},
        )

    def get(self, request, user):
        return self.render_page(request, user, SetPasswordForm(user))

    def post(self, request, user, token_hash):
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            if invites.activate(user, token_hash, form.cleaned_data["new_password1"]):
                request.session.pop(INVITE_SESSION_KEY, None)
                auth_login(request, user, backend=BACKEND_PATH)
                return redirect(settings.LOGIN_REDIRECT_URL)
            form.add_error(None, INVITE_GONE)
        return self.render_page(request, user, form)


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "auth/password_reset.pug"
    form_class = TenantPasswordResetForm
    email_template_name = "email/reset.txt.pug"
    success_url = reverse_lazy("password-reset-done")
    extra_context = {"title": "Reset password"}


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "auth/password_reset_done.pug"
    extra_context = {"title": "Reset password"}


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "auth/password_reset_confirm.pug"
    form_class = NewPasswordForm
    success_url = reverse_lazy("password-reset-complete")
    extra_context = {"title": "Choose a new password"}

    def form_valid(self, form):
        response = super().form_valid(form)
        audit(form.user, "user.password_reset", form.user)
        return response


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "auth/password_reset_complete.pug"
    extra_context = {"title": "Password changed"}


def forbidden(request, exception=None):
    return render(request, "errors/403.pug", status=403)


def not_found(request, exception=None):
    return render(request, "errors/404.pug", status=404)


def server_error(request):
    return render(request, "errors/500.pug", status=500)
