from django.urls import path

from projects.views import ProjectDetailView, WorkspaceProjectListView


urlpatterns = [
    path("workspaces/<slug:workspace_slug>/projects/", WorkspaceProjectListView.as_view(), name="workspace-project-list"),
    path("projects/<slug:slug>/", ProjectDetailView.as_view(), name="project-detail"),
]
