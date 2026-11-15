from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api.views import (
    ActivityViewSet,
    CommentViewSet,
    InvitationAcceptAPIView,
    ProjectArchiveAPIView,
    ProjectDetailAPIView,
    ProjectUnarchiveAPIView,
    ProjectViewSet,
    TaskArchiveAPIView,
    TaskBulkUpdateAPIView,
    TaskChecklistItemDetailAPIView,
    TaskChecklistItemToggleAPIView,
    TaskChecklistListCreateAPIView,
    TaskChecklistReorderAPIView,
    TaskDetailAPIView,
    TaskRestoreAPIView,
    TaskViewSet,
    WorkspaceActivityAPIView,
    WorkspaceInvitationListCreateAPIView,
    WorkspaceInvitationRevokeAPIView,
    WorkspaceMembershipDetailAPIView,
    WorkspaceOwnershipTransferAPIView,
    WorkspaceTagDetailAPIView,
    WorkspaceTagListCreateAPIView,
    WorkspaceViewSet,
)

router = DefaultRouter()
router.register("workspaces", WorkspaceViewSet, basename="api-workspace")
router.register("projects", ProjectViewSet, basename="api-project")
router.register("tasks", TaskViewSet, basename="api-task")
router.register("comments", CommentViewSet, basename="api-comment")
router.register("activity", ActivityViewSet, basename="api-activity")


urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path(
        "invitations/<uuid:token>/accept/",
        InvitationAcceptAPIView.as_view(),
        name="api-invitation-accept",
    ),
    path(
        "workspaces/<slug:slug>/activity/",
        WorkspaceActivityAPIView.as_view(),
        name="api-workspace-activity",
    ),
    path(
        "workspaces/<slug:slug>/invitations/",
        WorkspaceInvitationListCreateAPIView.as_view(),
        name="api-workspace-invitations",
    ),
    path(
        "workspaces/<slug:slug>/invitations/<int:invitation_id>/",
        WorkspaceInvitationRevokeAPIView.as_view(),
        name="api-workspace-invitation-detail",
    ),
    path(
        "workspaces/<slug:slug>/memberships/<int:membership_id>/",
        WorkspaceMembershipDetailAPIView.as_view(),
        name="api-workspace-membership-detail",
    ),
    path(
        "workspaces/<slug:slug>/transfer-ownership/",
        WorkspaceOwnershipTransferAPIView.as_view(),
        name="api-workspace-transfer-ownership",
    ),
    path(
        "workspaces/<slug:slug>/tags/",
        WorkspaceTagListCreateAPIView.as_view(),
        name="api-workspace-tags",
    ),
    path(
        "workspaces/<slug:slug>/tags/<int:tag_id>/",
        WorkspaceTagDetailAPIView.as_view(),
        name="api-workspace-tag-detail",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/",
        ProjectDetailAPIView.as_view(),
        name="api-project-detail",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/archive/",
        ProjectArchiveAPIView.as_view(),
        name="api-project-archive",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/unarchive/",
        ProjectUnarchiveAPIView.as_view(),
        name="api-project-unarchive",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/tasks/<slug:task_slug>/",
        TaskDetailAPIView.as_view(),
        name="api-task-detail",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/tasks/<slug:task_slug>/archive/",
        TaskArchiveAPIView.as_view(),
        name="api-task-archive",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/tasks/<slug:task_slug>/restore/",
        TaskRestoreAPIView.as_view(),
        name="api-task-restore",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/tasks/<slug:task_slug>/checklist/",
        TaskChecklistListCreateAPIView.as_view(),
        name="api-task-checklist",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/tasks/<slug:task_slug>/checklist/<int:item_id>/",
        TaskChecklistItemDetailAPIView.as_view(),
        name="api-task-checklist-detail",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/tasks/<slug:task_slug>/checklist/<int:item_id>/toggle/",
        TaskChecklistItemToggleAPIView.as_view(),
        name="api-task-checklist-toggle",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/tasks/<slug:task_slug>/checklist/reorder/",
        TaskChecklistReorderAPIView.as_view(),
        name="api-task-checklist-reorder",
    ),
    path(
        "tasks/bulk-update/",
        TaskBulkUpdateAPIView.as_view(),
        name="api-task-bulk-update",
    ),
    path("", include(router.urls)),
]
