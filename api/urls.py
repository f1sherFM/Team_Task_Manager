from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api.views import ActivityViewSet, CommentViewSet, ProjectViewSet, TaskViewSet, WorkspaceActivityAPIView, WorkspaceViewSet


router = DefaultRouter()
router.register("workspaces", WorkspaceViewSet, basename="api-workspace")
router.register("projects", ProjectViewSet, basename="api-project")
router.register("tasks", TaskViewSet, basename="api-task")
router.register("comments", CommentViewSet, basename="api-comment")
router.register("activity", ActivityViewSet, basename="api-activity")


urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("workspaces/<slug:slug>/activity/", WorkspaceActivityAPIView.as_view(), name="api-workspace-activity"),
    path("", include(router.urls)),
]
