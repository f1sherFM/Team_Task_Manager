from django.urls import path

from workspaces.views import (
    WorkspaceCreateView,
    WorkspaceDetailView,
    WorkspaceListView,
    WorkspaceMembersView,
)


urlpatterns = [
    path("", WorkspaceListView.as_view(), name="workspace-list"),
    path("create/", WorkspaceCreateView.as_view(), name="workspace-create"),
    path("<slug:slug>/members/", WorkspaceMembersView.as_view(), name="workspace-members"),
    path("<slug:slug>/", WorkspaceDetailView.as_view(), name="workspace-detail"),
]
