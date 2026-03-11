from django.urls import path

from activity.views import WorkspaceActivityView


urlpatterns = [
    path("workspaces/<slug:slug>/activity/", WorkspaceActivityView.as_view(), name="workspace-activity"),
]
