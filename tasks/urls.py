from django.urls import path

from tasks.views import (
    ProjectTaskListView,
    TaskDetailView,
    TaskStatusUpdateView,
    TaskUpdateView,
)

urlpatterns = [
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/tasks/",
        ProjectTaskListView.as_view(),
        name="project-task-list",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/tasks/<slug:task_slug>/",
        TaskDetailView.as_view(),
        name="task-detail",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/tasks/<slug:task_slug>/edit/",
        TaskUpdateView.as_view(),
        name="task-edit",
    ),
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/tasks/<slug:task_slug>/status/",
        TaskStatusUpdateView.as_view(),
        name="task-status-update",
    ),
]
