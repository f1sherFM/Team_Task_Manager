from django.urls import path

from accounts.views import AccountLoginView, AccountLogoutView, SignUpView


urlpatterns = [
    path("signup/", SignUpView.as_view(), name="signup"),
    path("login/", AccountLoginView.as_view(), name="login"),
    path("logout/", AccountLogoutView.as_view(), name="logout"),
]
