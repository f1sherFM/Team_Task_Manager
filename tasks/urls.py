from django.urls import path

from tasks.views import ProjectTaskListView, TaskDetailView, TaskUpdateView


urlpatterns = [
    path("projects/<slug:project_slug>/tasks/", ProjectTaskListView.as_view(), name="project-task-list"),
    path("tasks/<slug:slug>/", TaskDetailView.as_view(), name="task-detail"),
    path("tasks/<slug:slug>/edit/", TaskUpdateView.as_view(), name="task-edit"),
]
