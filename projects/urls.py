from django.urls import path

from projects.views import (
    ProjectArchiveView,
    ProjectDetailView,
    ProjectUnarchiveView,
    WorkspaceProjectListView,
)

urlpatterns = [
    path(
        "workspaces/<slug:workspace_slug>/projects/",
        WorkspaceProjectListView.as_view(),
        name="workspace-project-list",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/archive/",
        ProjectArchiveView.as_view(),
        name="project-archive",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/unarchive/",
        ProjectUnarchiveView.as_view(),
        name="project-unarchive",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/",
        ProjectDetailView.as_view(),
        name="project-detail",
    ),
]
