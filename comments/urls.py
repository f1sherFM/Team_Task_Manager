from django.urls import path

from comments.views import CommentCreateView, CommentDeleteView


urlpatterns = [
    path(
        "workspaces/<slug:workspace_slug>/projects/<slug:project_slug>/tasks/<slug:task_slug>/comments/add/",
        CommentCreateView.as_view(),
        name="comment-create",
    ),
    path("comments/<int:comment_id>/delete/", CommentDeleteView.as_view(), name="comment-delete"),
]
