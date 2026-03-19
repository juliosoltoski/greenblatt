from django.urls import path

from apps.accounts.views import AccountSettingsView, CsrfTokenView, CurrentUserView, LoginView, LogoutView


urlpatterns = [
    path("csrf/", CsrfTokenView.as_view(), name="auth-csrf"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", CurrentUserView.as_view(), name="auth-me"),
    path("settings/", AccountSettingsView.as_view(), name="auth-settings"),
]
