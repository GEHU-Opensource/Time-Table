from django.urls import path

from core import views

urlpatterns = [
    path("healthz/", views.health, name="health"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("invite/set-password/", views.InviteSetPasswordView.as_view(), name="invite-set-password"),
    path("invite/<str:token>/", views.InviteAcceptView.as_view(), name="invite-accept"),
    path("password-reset/", views.PasswordResetView.as_view(), name="password-reset"),
    path("password-reset/done/", views.PasswordResetDoneView.as_view(), name="password-reset-done"),
    path(
        "reset/<uidb64>/<token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("reset/done/", views.PasswordResetCompleteView.as_view(), name="password-reset-complete"),
    path("mfa/setup/", views.MfaSetupView.as_view(), name="mfa-setup"),
    path("mfa/verify/", views.MfaVerifyView.as_view(), name="mfa-verify"),
]
