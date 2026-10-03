from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

RESET_SUBJECT = "Reset your Time-Table password"


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )


class TotpTokenForm(forms.Form):
    token = forms.RegexField(
        label="Authenticator code",
        regex=r"^\d{6}$",
        widget=forms.TextInput(
            attrs={"inputmode": "numeric", "autocomplete": "one-time-code", "autofocus": True}
        ),
        error_messages={"invalid": "Enter the 6-digit code from your authenticator app."},
    )


class NewPasswordForm(SetPasswordForm):
    def save(self, commit=True):
        self.user.set_password(self.cleaned_data["new_password1"])
        self.user.auth_version += 1
        if commit:
            self.user.save(update_fields=["password", "auth_version"])
        return self.user


class TenantPasswordResetForm(PasswordResetForm):
    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        body = render_to_string(email_template_name, context)
        EmailMessage(RESET_SUBJECT, body, from_email, [to_email]).send()
