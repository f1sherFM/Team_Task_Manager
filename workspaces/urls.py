from django.urls import path

from activity.views import WorkspaceActivityView
from workspaces.views import (
    WorkspaceCreateView,
    WorkspaceDetailView,
    WorkspaceInvitationRevokeView,
    WorkspaceListView,
    WorkspaceMembershipRemoveView,
    WorkspaceMembershipRoleUpdateView,
    WorkspaceMembersView,
    WorkspaceOwnershipTransferView,
)

urlpatterns = [
    path("", WorkspaceListView.as_view(), name="workspace-list"),
    path("create/", WorkspaceCreateView.as_view(), name="workspace-create"),
    path("<slug:slug>/activity/", WorkspaceActivityView.as_view(), name="workspace-activity"),
    path("<slug:slug>/members/", WorkspaceMembersView.as_view(), name="workspace-members"),
    path(
        "<slug:slug>/members/<int:membership_id>/role/",
        WorkspaceMembershipRoleUpdateView.as_view(),
        name="workspace-membership-role-update",
    ),
    path(
        "<slug:slug>/members/<int:membership_id>/remove/",
        WorkspaceMembershipRemoveView.as_view(),
        name="workspace-membership-remove",
    ),
    path(
        "<slug:slug>/invitations/<int:invitation_id>/revoke/",
        WorkspaceInvitationRevokeView.as_view(),
        name="workspace-invitation-revoke",
    ),
    path(
        "<slug:slug>/transfer-ownership/",
        WorkspaceOwnershipTransferView.as_view(),
        name="workspace-transfer-ownership",
    ),
    path("<slug:slug>/", WorkspaceDetailView.as_view(), name="workspace-detail"),
]
