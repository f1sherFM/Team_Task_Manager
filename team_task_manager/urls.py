from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.views import HomeView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("accounts/", include("accounts.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("api/", include("api.urls")),
    path("workspaces/", include("workspaces.urls")),
    path("", include("comments.urls")),
    path("", include("projects.urls")),
    path("", include("tasks.urls")),
    path("admin/", admin.site.urls),
]
