from django.contrib import admin
from django.urls import include, path

from core.views import HomeView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("accounts/", include("accounts.urls")),
    path("workspaces/", include("workspaces.urls")),
    path("", include("projects.urls")),
    path("", include("tasks.urls")),
    path("admin/", admin.site.urls),
]
